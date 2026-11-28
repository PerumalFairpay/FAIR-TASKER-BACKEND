import json
import os
import re
from datetime import datetime, date
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple

from bson import ObjectId
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from app.database import db, employees_collection
from app.services.ai_collection_catalog import (
    COLLECTION_CATALOG,
    get_collection_catalog_summary,
    find_collections_by_intent,
)
from app.services.api import DocumentService
from app.services.vector_store import vector_store_service


BLACKLIST_COLLECTIONS = {
    "chat_sessions",
    "chat_messages",
    "permissions",
    "role_permissions",
    "user_permissions",
    "nda_requests",
    "pending_biometric_logs",
    "checklist_templates",
    "system_configurations",
    "employee_documents",
    "ticket_messages",
}

SENSITIVE_FIELDS = {
    "hashed_password",
    "password",
    "token",
    "secret",
    "otp_code",
    "otp_secret",
    "reset_token",
    "refresh_token",
    "access_token",
    "signature_data",
}

PUBLIC_COLLECTIONS = {
    "departments",
    "shifts",
    "leave_types",
    "holidays",
    "blogs",
    "documents",
    "document_categories",
    "asset_categories",
}

ADMIN_ONLY_COLLECTIONS = {
    "users",
    "roles",
    "clients",
    "payslip_components",
    "expenses",
    "expense_categories",
}

PERSONAL_SCOPED_COLLECTIONS = {
    "employees",
    "attendance",
    "leave_requests",
    "wfh_requests",
    "payslips",
    "tasks",
    "projects",
    "eod_reports",
    "assets",
    "tickets",
    "feedback",
}

FORBIDDEN_MONGO_OPERATORS = {
    "$out",
    "$merge",
    "$where",
    "$function",
    "$accumulator",
}


def _get_allowed_collections(is_admin: bool) -> List[str]:
    """Returns the list of queryable collection names for the current user's role."""
    if is_admin:
        return [c for c in COLLECTION_CATALOG.keys() if c not in BLACKLIST_COLLECTIONS]
    return [
        c for c in COLLECTION_CATALOG.keys()
        if c not in BLACKLIST_COLLECTIONS and c not in ADMIN_ONLY_COLLECTIONS
    ]


def _contains_forbidden_operator(obj: Any) -> Optional[str]:
    """Recursively checks a MongoDB query/pipeline dict or list for forbidden operators."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.strip().lower() in FORBIDDEN_MONGO_OPERATORS:
                return k
            found = _contains_forbidden_operator(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _contains_forbidden_operator(item)
            if found:
                return found
    return None


def _sanitize_value(val: Any) -> Any:
    """Recursively converts BSON/datetime types to JSON-safe values and strips sensitive fields."""
    if isinstance(val, ObjectId):
        return str(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, list):
        return [_sanitize_value(item) for item in val]
    if isinstance(val, dict):
        cleaned = {}
        for k, v in val.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_FIELDS:
                continue
            cleaned[k] = _sanitize_value(v)
        return cleaned
    return val


def _build_scope_filter(
    collection_name: str,
    is_admin: bool,
    emp_id_str: Optional[str],
    emp_no_id: Optional[str],
    user_id: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Builds a mandatory ownership/visibility filter for non-admin users.
    Returns (filter_dict, error_message).
    """
    if is_admin:
        return None, None

    if collection_name in PUBLIC_COLLECTIONS:
        if collection_name == "documents":
            return {"status": "Active"}, None
        return None, None

    if collection_name in ADMIN_ONLY_COLLECTIONS or collection_name not in PERSONAL_SCOPED_COLLECTIONS:
        return None, f"Access Denied: Collection '{collection_name}' is restricted to administrators."

    if collection_name == "employees":
        if emp_no_id:
            return {"employee_no_id": emp_no_id}, None
        if emp_id_str and ObjectId.is_valid(emp_id_str):
            return {"_id": ObjectId(emp_id_str)}, None
        return None, "Access Denied: Unable to resolve your employee record."

    if collection_name == "attendance":
        ids = [x for x in [emp_id_str, emp_no_id] if x]
        if not ids:
            return None, "Access Denied: Unable to resolve your employee ID for attendance."
        return {"employee_id": {"$in": ids}}, None

    if collection_name in {"leave_requests", "wfh_requests", "payslips"}:
        if not emp_id_str:
            return None, f"Access Denied: Unable to resolve your employee ID for {collection_name}."
        return {"employee_id": emp_id_str}, None

    if collection_name in {"tasks", "eod_reports", "assets"}:
        if not emp_id_str:
            return None, f"Access Denied: Unable to resolve your employee ID for {collection_name}."
        return {"assigned_to": emp_id_str}, None

    if collection_name == "projects":
        if not emp_id_str:
            return None, "Access Denied: Unable to resolve your employee ID for projects."
        return {"team_members": emp_id_str}, None

    if collection_name == "tickets":
        ids = [x for x in [user_id, emp_id_str] if x]
        if not ids:
            return None, "Access Denied: Unable to resolve your identity for tickets."
        return {"$or": [{"requester_id": {"$in": ids}}, {"assigned_to": {"$in": ids}}]}, None

    if collection_name == "feedback":
        if not user_id:
            return None, "Access Denied: Unable to resolve your user ID for feedback."
        return {"user_id": user_id}, None

    return None, f"Access Denied: Collection '{collection_name}' is not accessible."


async def _inspect_collection_fields(collection_name: str, limit_samples: int = 3) -> List[str]:
    """Samples up to `limit_samples` non-deleted documents to infer field names and types."""
    try:
        docs = await db[collection_name].find(
            {"is_deleted": {"$ne": True}}
        ).limit(limit_samples).to_list(length=limit_samples)
        field_types: Dict[str, str] = {}
        for doc in docs:
            for k, v in doc.items():
                if k.lower() in SENSITIVE_FIELDS:
                    continue
                t_name = type(v).__name__
                if k not in field_types:
                    field_types[k] = t_name
        return [f"{k} ({t})" for k, t in field_types.items()]
    except Exception:
        return []


async def get_tools_for_user(user: dict, current_query: Optional[str] = None):
    """Returns dynamic MongoDB query + RAG tools scoped strictly to the user's role."""
    role = (user.get("role") or "employee").lower()
    is_admin = role == "admin"
    emp_no_id = user.get("employee_no_id")
    user_id = str(user.get("id") or user.get("_id") or "")

    # Resolve canonical employee ObjectId string once for strict RBAC scoping
    emp_id_str: Optional[str] = None
    if emp_no_id:
        emp_doc = await employees_collection.find_one(
            {"employee_no_id": emp_no_id, "is_deleted": {"$ne": True}},
            {"_id": 1}
        )
        if emp_doc:
            emp_id_str = str(emp_doc["_id"])

    allowed_collections = _get_allowed_collections(is_admin)

    @tool
    async def get_database_schema(collection_names: Optional[List[str]] = None) -> str:
        """
        Retrieves schema info (collection descriptions, field names, and inferred types) for MongoDB collections.
        Specify `collection_names` for only the collections you need (e.g. ["employees", "leave_requests"]).
        If `collection_names` is omitted, returns the catalog of all collections you are permitted to query.
        """
        try:
            if not collection_names:
                catalog_text = get_collection_catalog_summary(allowed_collections)
                return (
                    "=== AVAILABLE DATABASE COLLECTIONS ===\n"
                    f"{catalog_text}\n\n"
                    "Call `get_database_schema(collection_names=['collection_name', ...])` to inspect exact fields before running a query."
                )

            allowed_set = set(allowed_collections)
            target_cols = [c for c in collection_names if c in allowed_set]
            if not target_cols:
                return f"None of the requested collections are accessible. Available collections: {', '.join(allowed_collections)}"

            schema_blocks = []
            for col_name in target_cols:
                meta = COLLECTION_CATALOG.get(col_name, {})
                desc = meta.get("description", "")
                avoid = meta.get("avoid_for", "")
                fields = await _inspect_collection_fields(col_name)
                block = f"Collection: `{col_name}`\nDescription: {desc}"
                if avoid:
                    block += f"\nRule: {avoid}"
                if fields:
                    block += f"\nSampled Fields: {', '.join(fields)}"
                else:
                    block += "\nSampled Fields: (collection currently empty or no non-deleted docs; use catalog description)"
                schema_blocks.append(block)

            return "\n\n".join(schema_blocks)
        except Exception as e:
            return f"Error reading database schema: {str(e)}"

    @tool
    async def execute_read_only_query(
        collection: str,
        operation: str = "find",
        query_json: str = "{}",
        projection_json: Optional[str] = None,
        sort_json: Optional[str] = None,
        limit: int = 30,
    ) -> str:
        """
        Executes a safe, read-only MongoDB query (`find` or `aggregate`) and returns compact JSON.
        - collection: Target MongoDB collection name.
        - operation: "find" (default) or "aggregate".
        - query_json: JSON string. For "find", a MongoDB filter object (e.g. '{"status": "Pending"}').
          For "aggregate", a JSON array of pipeline stages (e.g. '[{"$group": {"_id": "$status", "count": {"$sum": 1}}}]').
        - projection_json: Optional JSON object of fields to include/exclude for "find" (e.g. '{"full_name": 1, "designation": 1}').
        - sort_json: Optional JSON object of sort order for "find" (e.g. '{"created_at": -1}').
        - limit: Max rows to return (default 30, capped at 100).
        NOTE: Soft-delete (`is_deleted != True`) and user-role ownership filters are enforced automatically in code.
        """
        col_name = (collection or "").strip()
        op = (operation or "find").strip().lower()

        if col_name in BLACKLIST_COLLECTIONS or col_name not in allowed_collections:
            return f"Access Denied: Collection '{col_name}' is not accessible for your role."

        if op not in ("find", "aggregate"):
            return "Error: Only 'find' and 'aggregate' read-only operations are permitted."

        try:
            parsed_query = json.loads(query_json) if query_json else ({} if op == "find" else [])
        except json.JSONDecodeError as e:
            return f"Error: Invalid `query_json`: {str(e)}"

        if op == "find" and not isinstance(parsed_query, dict):
            return "Error: For 'find' operation, `query_json` must be a JSON object (filter dict)."
        if op == "aggregate" and not isinstance(parsed_query, list):
            return "Error: For 'aggregate' operation, `query_json` must be a JSON array of pipeline stages."

        forbidden_op = _contains_forbidden_operator(parsed_query)
        if forbidden_op:
            return f"Error: Forbidden MongoDB operator '{forbidden_op}' detected. Only read-only queries are allowed."

        # Non-admin $lookup guardrail: prevent cross-collection joins into restricted/personal data
        if op == "aggregate" and not is_admin:
            for stage in parsed_query:
                if isinstance(stage, dict) and "$lookup" in stage:
                    lookup_cfg = stage["$lookup"]
                    target_from = lookup_cfg.get("from") if isinstance(lookup_cfg, dict) else None
                    if target_from not in PUBLIC_COLLECTIONS:
                        return (
                            f"Access Denied: Cross-collection $lookup to '{target_from}' is not permitted for your role. "
                            f"Only public reference collections ({', '.join(sorted(PUBLIC_COLLECTIONS))}) can be joined."
                        )

        # Build mandatory RBAC + soft-delete guard filter
        scope_filter, scope_err = _build_scope_filter(col_name, is_admin, emp_id_str, emp_no_id, user_id)
        if scope_err:
            return scope_err

        user_intent_text = (current_query or "").lower()
        asks_for_deleted = is_admin and any(
            w in user_intent_text for w in ["deleted", "trash", "archived", "soft delete", "including deleted"]
        )

        guard_clauses: List[Dict[str, Any]] = []
        if not asks_for_deleted:
            guard_clauses.append({"is_deleted": {"$ne": True}})
        if scope_filter:
            guard_clauses.append(scope_filter)

        safe_limit = min(max(int(limit or 30), 1), 100)

        try:
            target_col = db[col_name]

            if op == "find":
                if guard_clauses and parsed_query:
                    final_filter: Dict[str, Any] = {"$and": [parsed_query, *guard_clauses]}
                elif guard_clauses:
                    final_filter = guard_clauses[0] if len(guard_clauses) == 1 else {"$and": guard_clauses}
                else:
                    final_filter = parsed_query

                projection = None
                if projection_json:
                    try:
                        parsed_proj = json.loads(projection_json)
                        if isinstance(parsed_proj, dict):
                            projection = {
                                k: v for k, v in parsed_proj.items()
                                if isinstance(k, str) and k.lower() not in SENSITIVE_FIELDS
                            }
                    except json.JSONDecodeError:
                        return "Error: Invalid `projection_json`."

                cursor = target_col.find(final_filter, projection)

                if sort_json:
                    try:
                        parsed_sort = json.loads(sort_json)
                        if isinstance(parsed_sort, dict) and parsed_sort:
                            cursor = cursor.sort(list(parsed_sort.items()))
                    except json.JSONDecodeError:
                        return "Error: Invalid `sort_json`."

                rows = await cursor.limit(safe_limit).to_list(length=safe_limit)
            else:
                pipeline = list(parsed_query)
                if guard_clauses:
                    guard_match = guard_clauses[0] if len(guard_clauses) == 1 else {"$and": guard_clauses}
                    pipeline.insert(0, {"$match": guard_match})

                # Ensure output is bounded
                has_limit_stage = any(isinstance(s, dict) and "$limit" in s for s in pipeline)
                if not has_limit_stage:
                    pipeline.append({"$limit": safe_limit})
                else:
                    for s in pipeline:
                        if isinstance(s, dict) and "$limit" in s and isinstance(s["$limit"], int):
                            s["$limit"] = min(s["$limit"], 100)

                rows = await target_col.aggregate(pipeline).to_list(length=safe_limit)

            if not rows:
                return json.dumps({
                    "status": "success",
                    "rows_returned": 0,
                    "message": "Query executed successfully. 0 documents matched.",
                    "diagnostic_hint": "Verify field names with get_database_schema, check case-insensitive regex filters ($regex with $options: 'i'), or check date formats (YYYY-MM-DD)."
                })

            sanitized_rows = [_sanitize_value(r) for r in rows]
            return json.dumps(sanitized_rows, separators=(",", ":"))
        except Exception as e:
            return f"Database query failed: {str(e)}"

    @tool
    async def search_document_content(
        query: str,
        category_id: Optional[str] = None,
        limit: int = 5
    ):
        """
        Searches INSIDE the actual text content of company documents (policies, handbooks, manuals, agreements) for answers.
        """
        try:
            filter_dict: Dict[str, Any] = {"category_id": category_id} if category_id else {}

            if not is_admin:
                active_docs, _ = await DocumentService.list(status="Active")
                active_doc_ids = [str(doc["id"]) for doc in (active_docs or [])]
                if not active_doc_ids:
                    return "No relevant active documents found to search."
                filter_dict["document_id"] = active_doc_ids

            results = await vector_store_service.search_documents(query=query, filter_dict=filter_dict, limit=limit)
            if not results:
                return f"No relevant information found inside documents for '{query}'."
            return results
        except Exception as e:
            return f"Error searching document content: {str(e)}"

    return [get_database_schema, execute_read_only_query, search_document_content]


async def chat_stream(query: str, history: list, user: dict) -> AsyncGenerator[str, None]:
    """Generates a streaming response using LangGraph ReAct agent with dynamic MongoDB queries."""

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        yield "Error: GEMINI_API_KEY or GOOGLE_API_KEY environment variable is not set on the server."
        return

    model_name = (
        os.environ.get("GEMINI_FLASH_MODEL")
        or os.environ.get("GEMINI_MODEL")
        or "gemini-2.5-flash"
    )
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.1,
        streaming=True,
    )

    last_context = ""
    if history and len(history) > 0:
        last_context = history[-1].get("content", "")
    full_context_text = f"{last_context} {query}".strip()

    role = (user.get("role") or "employee").lower()
    is_admin = role == "admin"
    allowed_collections = _get_allowed_collections(is_admin)

    tools = await get_tools_for_user(user, current_query=full_context_text)

    # Dynamic schema pre-loading based on detected intent
    matched_cols = find_collections_by_intent(full_context_text, allowed_collections, top_k=5)
    dynamic_schema_lines = []
    for col_name in matched_cols:
        meta = COLLECTION_CATALOG.get(col_name, {})
        desc = meta.get("description", "")
        avoid = meta.get("avoid_for", "")
        fields = await _inspect_collection_fields(col_name)
        entry = f"• Collection: `{col_name}`\n  Description: {desc}"
        if avoid:
            entry += f"\n  ANTI-HALLUCINATION RULE: {avoid}"
        if fields:
            entry += f"\n  Sampled Fields: {', '.join(fields)}"
        dynamic_schema_lines.append(entry)

    dynamic_schema_context = (
        "\n\n".join(dynamic_schema_lines)
        if dynamic_schema_lines
        else "None pre-loaded. Call `get_database_schema()` to see available collections."
    )

    today = datetime.now().strftime("%Y-%m-%d, %A")
    access_scope_note = (
        "Full organization-wide read access across allowed HRM collections."
        if is_admin
        else "STRICT EMPLOYEE SCOPE: You may ONLY access this employee's own personal records (profile, attendance, leaves, WFH, payslips, tasks, projects, EOD reports, assets, tickets, feedback) and public company data (holidays, blogs, departments, shifts, leave types, active documents). Never fabricate or infer other employees' data."
    )

    system_prompt = (
        "You are the Fyro AI Assistant, a friendly, sharp, and super-helpful workplace & HRM sidekick! "
        "Keep your tone warm, clear, and engaging (light humor/emojis where appropriate, while staying accurate and professional with numbers and policies)."
        f"\nCurrent User: {user.get('name', 'User')} (Role: {role})"
        f"\nAccess Scope: {access_scope_note}"
        f"\nCurrent Date: {today}"
        "\n\nCRITICAL PRIVACY & TRANSPARENCY RULES:"
        "\n- NEVER mention internal tool names (`get_database_schema`, `execute_read_only_query`, `search_document_content`), collection names, MongoDB syntax, or backend implementation details to the user."
        "\n- STRICT FACTUAL GROUNDING: Every count, name, date, and metric MUST come directly from query/document search results. Never guess or fabricate numbers."
        "\n- If a non-admin employee asks for another employee's private data (salary, attendance, leaves, profile), politely let them know you can only share their own personal details and company-wide information."
        "\n\n=== RELEVANT DATABASE COLLECTIONS FOR CURRENT QUESTION (PRE-LOADED) ==="
        f"\n{dynamic_schema_context}"
        "\n\nQUERY EXECUTION GUIDELINES:"
        "\n1. Schema Discovery: If you need collections not pre-loaded above, call `get_database_schema(collection_names=[...])` (or omit `collection_names` to see the full allowed catalog) before querying."
        "\n2. Dynamic MongoDB Queries: Use `execute_read_only_query` with `operation='find'` for filtered lists or `operation='aggregate'` for counts/grouping/summaries (use `$group`, `$count`, `$sum`, `$avg` in MongoDB instead of fetching all documents)."
        "\n3. Text Matching: Use case-insensitive regex `{\"$regex\": \"...\", \"$options\": \"i\"}` when matching names, titles, or statuses."
        "\n4. Document / Policy Questions: If the user asks about company policies, handbooks, rules, or agreements, use `search_document_content`."
        "\n5. Leave Advice: If an employee asks what kind of leave to take, check their `employees` record (leave balances) and `leave_types`."
        "\n\nDATA PRESENTATION & FORMATTING:"
        "\n1. Use clean Markdown tables for multi-row datasets (3+ records). Keep tables readable (split into logical tables if >6-7 columns)."
        "\n2. Use bullet points or bold key-value pairs for single records or 1-2 item summaries."
        "\n3. Bold key figures and metrics (e.g., **12 Pending Leaves**, **95% Attendance**)."
        "\n\nINTERACTIVE CHARTS & FOLLOW-UP SUGGESTIONS:"
        "\n- When the user asks for a breakdown, distribution, trend, or summary with 2+ categories, you may include a `<chart>{...}</chart>` JSON block (`type`: `bar`|`pie`|`line`|`area`, `title`, `xAxis`, `data`, `series`). Do not include charts for single numbers or yes/no answers."
        "\n- At the end of your response, you may include 2-3 contextual follow-up questions in `<suggestions>[\"Question 1?\", \"Question 2?\"]</suggestions>`."
    )

    agent = create_react_agent(llm, tools, prompt=system_prompt)

    try:
        MAX_HISTORY = 6
        trimmed_history = history[-MAX_HISTORY:] if len(history) > MAX_HISTORY else history

        langchain_messages = []
        for msg in trimmed_history:
            msg_role = msg.get("role")
            content = msg.get("content")
            if msg_role and content:
                cleaned_content = re.sub(r"<chart>.*?</chart>", "", content, flags=re.DOTALL)
                cleaned_content = re.sub(r"<suggestions>.*?</suggestions>", "", cleaned_content, flags=re.DOTALL)
                cleaned_content = cleaned_content.strip()
                if cleaned_content:
                    mapped_role = "human" if msg_role == "user" else "assistant"
                    langchain_messages.append((mapped_role, cleaned_content))

        langchain_messages.append(("human", query))

        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        llm_call_count = 0

        async for event in agent.astream_events(
            {"messages": langchain_messages},
            config={"recursion_limit": 40},
            version="v2"
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                if "chunk" in event["data"]:
                    content = event["data"]["chunk"].content
                    if isinstance(content, str) and content:
                        yield content
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text = part.get("text", "")
                                if text:
                                    yield text
            elif kind == "on_chat_model_end":
                llm_call_count += 1
                output = event.get("data", {}).get("output")
                usage = None
                if hasattr(output, "usage_metadata") and output.usage_metadata:
                    usage = output.usage_metadata
                elif hasattr(output, "response_metadata") and output.response_metadata:
                    usage = output.response_metadata.get("usage_metadata") or output.response_metadata.get("token_usage")
                elif isinstance(output, dict):
                    usage = output.get("usage_metadata") or output.get("response_metadata", {}).get("usage_metadata")

                if usage and isinstance(usage, dict):
                    inp = usage.get("input_tokens") or usage.get("prompt_tokens") or usage.get("prompt_token_count") or 0
                    out = usage.get("output_tokens") or usage.get("completion_tokens") or usage.get("candidates_token_count") or 0
                    tot = usage.get("total_tokens") or usage.get("total_token_count") or (inp + out)
                    total_input_tokens += inp
                    total_output_tokens += out
                    total_tokens += tot

        trunc_query = (query[:60] + "...") if len(query) > 60 else query
        if total_tokens > 0 or total_input_tokens > 0:
            print(
                f"\n{'='*65}\n"
                f"[AI TOKEN USAGE] Query: \"{trunc_query}\"\n"
                f"  • Model             : {model_name}\n"
                f"  • LLM Step Calls    : {llm_call_count}\n"
                f"  • Prompt Tokens     : {total_input_tokens:,}\n"
                f"  • Completion Tokens : {total_output_tokens:,}\n"
                f"  • Total Tokens      : {total_tokens:,}\n"
                f"{'='*65}\n",
                flush=True
            )
    except Exception as e:
        yield f"\n\n[Error communicating with AI: {str(e)}]"
