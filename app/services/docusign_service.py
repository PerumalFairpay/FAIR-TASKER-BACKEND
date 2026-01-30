
import os
import base64
from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition, Document, Signer, SignHere, Tabs, Recipients, RecipientViewRequest
from app import config

class DocuSignService:
    def __init__(self):
        pass

    def _get_authenticated_client(self):
        # 0. Sanitize Config
        integration_key = config.DOCUSIGN_INTEGRATION_KEY.strip()
        user_id = config.DOCUSIGN_USER_ID.strip()
        account_id = config.DOCUSIGN_API_ACCOUNT_ID.strip()
        base_path = config.DOCUSIGN_BASE_PATH.strip()
        private_key_path = config.DOCUSIGN_PRIVATE_KEY_PATH.strip()

        # 1. Auth Client (Only for Token & UserInfo)
        auth_client = ApiClient()
        auth_client.set_base_path(base_path) 

        # 2. Read Key
        try:
            with open(private_key_path, "r") as f:
                private_key = f.read().encode("ascii")
        except Exception as e:
            raise Exception(f"Private Key Error: {str(e)}")

        # 3. Request Token
        try:
            token_response = auth_client.request_jwt_user_token(
                client_id=integration_key,
                user_id=user_id,
                oauth_host_name="account-d.docusign.com", 
                private_key_bytes=private_key,
                expires_in=3600,
                scopes=["signature", "impersonation"]
            )
            access_token = token_response.access_token
            # Set auth header for Auth Client to get user info
            auth_client.set_default_header("Authorization", f"Bearer {access_token}")
        except Exception as e:
             raise Exception(f"JWT Auth Failed: {str(e)}")

        # 4. Dynamic Base Path Resolution
        try:
            user_info = auth_client.get_user_info(access_token)
            selected_account = next((acc for acc in user_info.accounts if acc.account_id == account_id), None)
            
            if not selected_account:
                 raise Exception(f"Account {account_id} not found for user")
            
            new_base_path = selected_account.base_uri + "/restapi"
            print(f"DocuSign Service: Authenticated. Using Base Path: {new_base_path}")
            
            # 5. Create FINAL Fresh Client (Clean State)
            # We do NOT reuse auth_client to avoid host/connection poisoning
            final_client = ApiClient()
            final_client.host = new_base_path # Explicitly set host property
            final_client.set_default_header("Authorization", f"Bearer {access_token}")
            
            # 6. Connectivity Check (Self-Test)
            try:
                # Use EnvelopesApi to verify real API access
                test_api = EnvelopesApi(final_client)
                test_api.list_status_changes(account_id, from_date="2025-01-01")
                print("DEBUG: Connection Self-Test PASSED on Final Client")
            except Exception as e:
                print(f"DEBUG: Connection Self-Test FAILED on Final Client: {str(e)}")
                # Raise to be safe, as 401 here guarantees 401 later.
                raise Exception(f"Final Client Access Check Failed: {str(e)}")
            
            return final_client

        except Exception as e:
            raise Exception(f"Auth/Resolution Failed: {str(e)}")

    def generate_nda_html(self, employee_data: dict) -> str:
        # Replicating the provided NDA layout
        # Using inline CSS for email/doc compatibility
        
        date_str = employee_data.get("join_date", "________________")
        emp_name = employee_data.get("name", "________________")
        emp_address = employee_data.get("address", "________________, ________________")
        emp_father = employee_data.get("father_name", "________________")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Arial', sans-serif; font-size: 11pt; color: #000; line-height: 1.4; }}
                .container {{ width: 100%; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ border-bottom: 2px solid #999; padding-bottom: 10px; margin-bottom: 20px; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #555; }} 
                .logo span {{ color: #4da6ff; }} /* Simulate the blue in logo */
                .title {{ text-align: center; font-weight: bold; margin: 20px 0; text-transform: uppercase; }}
                .section {{ margin-bottom: 15px; text-align: justify; }}
                .bold {{ font-weight: bold; }}
                .parties {{ margin-bottom: 20px; }}
                .clause {{ margin-bottom: 10px; display: flex; }}
                .clause-num {{ width: 30px; font-weight: bold; }}
                .clause-text {{ flex: 1; }}
                .signatures {{ margin-top: 50px; display: flex; justify-content: space-between; }}
                .sign-box {{ width: 45%; }}
                .sign-line {{ border-top: 1px solid #000; margin-top: 40px; padding-top: 5px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <!-- Placeholder for Logo - In a real scenario, use base64 encoded image or public URL -->
                    <div class="logo">Fair<span>PAY</span> <br> <span style="font-size: 14px; letter-spacing: 2px;">TECHWORKS</span></div>
                </div>

                <div class="title">NON-DISCLOSURE AGREEMENT (NDA)</div>

                <div class="section">
                    This Non-Disclosure Agreement (hereinafter "Agreement") is made {date_str}, as indicated below, and by and between:
                </div>

                <div class="parties">
                    <div class="section">
                        <span class="bold">FAIRPAY TECH WORKS</span>, a registered company in India, Tamil Nadu, Chennai – 600 113, (hereinafter referred to as "<span class="bold">FIRST PARTY</span>").
                    </div>
                    <!-- Added strictly as per image text, assuming these are standard affiliates -->
                    <div class="section">
                        <span class="bold">FAIRPY INC</span>, a registered company in USA, 880 SW 15th St #3, Forest Lake MN 55025, USA, (hereinafter referred to as "<span class="bold">FIRST PARTY</span>").
                    </div>
                    
                    <div class="section">
                        And
                    </div>

                    <div class="section">
                        <span class="bold">{emp_name}</span>, S/O <span class="bold">{emp_father}</span>, at {emp_address}, is a full-time employee of company <span class="bold">FAIRPAY TECH WORKS</span> in Chennai – 600 113, India. (Hereinafter referred to as "<span class="bold">SECOND PARTY</span>")
                    </div>
                </div>

                <div class="section">
                    WHEREAS, in consideration of the premises and of the covenants and obligations hereinafter set forth, First Party (FairPay Tech Works, Fairpy Inc, FairReturns & Fairental) and Second party (<span class="bold">{emp_name}</span>) hereto, intending to be legally bound, agree as follows:
                </div>

                <div class="clause">
                    <div class="clause-num">1.</div>
                    <div class="clause-text">For the purpose of this Agreement, <span class="bold">Information</span> shall mean any and all sorts of information (whether financial, marketing, business, economical, technical, design, commercial or of any nature) relating to <span class="bold">{emp_name}</span>.</div>
                </div>
                
                <div class="clause">
                    <div class="clause-num">2.</div>
                    <div class="clause-text"><span class="bold">{emp_name}</span> means: all <span class="bold">Information</span> in a written, oral, visual or tangible form disclosed to by either party from time to time after the Effective Date of this agreement and the delivery of any proposals to the other party concerning (FairPAY Tech Works, Fairpy Inc, FairReturns & Fairental) whether identified at time of disclosure and marked confidential or not.</div>
                </div>

                <div class="clause">
                    <div class="clause-num">3.</div>
                    <div class="clause-text">
                        <span class="bold">{emp_name} agrees</span> that he/she shall:
                        <br><br>
                        (i) keep Confidential Information and not to share it with any other third party whether orally or in writing without the written consent and prior approval of the other party.
                        <br><br>
                        (ii) not to use the Confidential Information for any commercial purpose including directly or indirectly.
                         <br><br>
                        (iii) not to use any of FairPAY Tech Works, Fairpy Inc, FairReturns & Fairental 's name or reference in any of current or future marketing tools or website.
                         <br><br>
                        (iv) to safeguard and not misuse any devices, equipment, or office property provided by the disclosing party, and to return the same in good working condition upon request or upon termination of engagement;
                         <br><br>
                        (v) to be solely responsible and liable for the care, use, and protection of such devices, equipment, and office property until their proper handover to the disclosing party.
                    </div>
                </div>

                <div class="signatures">
                    <div class="sign-box">
                        <div style="margin-bottom: 40px;">Signed for and in behalf of <br> <span class="bold">FAIRPAY TECH WORKS</span></div>
                        <img src="" alt="" style="height: 50px; display:block;"> <!-- Placeholder for CEO signature if needed -->
                        <div class="sign-line">Authorized Signatory</div>
                    </div>
                    <div class="sign-box">
                         <div style="margin-bottom: 40px;">Signed by <br> <span class="bold">{emp_name}</span></div>
                        <!-- Anchor string for DocuSign -->
                        <span style="color:white;">/sn1/</span> 
                        <div class="sign-line">Signature</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def send_nda_for_embedded_signing(self, employee_data: dict, return_url: str):
        # 0. Get Authenticated Client (Fresh per request)
        api_client = self._get_authenticated_client()
        account_id = config.DOCUSIGN_API_ACCOUNT_ID.strip()
        
        # 1. Create Document
        html_content = self.generate_nda_html(employee_data)
        document_base64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
        
        document = Document(
            document_base64=document_base64,
            name="NDA Agreement",
            file_extension="html",
            document_id="1"
        )

        # 2. Create Signer
        signer = Signer(
            email=employee_data['email'],
            name=employee_data['name'],
            client_user_id=employee_data['id'], # Setting this makes it embedded
            recipient_id="1"
        )

        # 3. Create Tabs (SignHere)
        # Using Anchor Tagging to place signature relative to hidden text in HTML
        sign_here = SignHere(
            anchor_string="/sn1/",
            anchor_units="pixels",
            anchor_y_offset="0",
            anchor_x_offset="0"
        )
        tabs = Tabs(sign_here_tabs=[sign_here])
        signer.tabs = tabs

        # 4. Create Envelope Definition
        envelope_definition = EnvelopeDefinition(
            email_subject="Please sign the NDA",
            documents=[document],
            recipients=Recipients(signers=[signer]),
            status="sent" # Sent creates it immediately
        )

        # 5. Create Envelope via API
        envelopes_api = EnvelopesApi(api_client)
        results = envelopes_api.create_envelope(account_id=account_id, envelope_definition=envelope_definition)
        envelope_id = results.envelope_id

        # 6. Create Recipient View (URL for iframe/redirect)
        recipient_view_request = RecipientViewRequest(
            authentication_method="none",
            client_user_id=employee_data['id'],
            recipient_id="1",
            return_url=return_url,
            user_name=employee_data['name'],
            email=employee_data['email']
        )
        
        view_results = envelopes_api.create_recipient_view(
            account_id=account_id,
            envelope_id=envelope_id,
            recipient_view_request=recipient_view_request
        )
        
        return view_results.url, envelope_id

    def get_envelope_status(self, envelope_id: str):
        api_client = self._get_authenticated_client()
        account_id = config.DOCUSIGN_API_ACCOUNT_ID.strip()
        envelopes_api = EnvelopesApi(api_client)
        
        try:
            envelope = envelopes_api.get_envelope(account_id=account_id, envelope_id=envelope_id)
            return envelope.status
        except Exception as e:
            print(f"Error getting envelope status: {str(e)}")
            return None

    def get_envelope_document(self, envelope_id: str):
        api_client = self._get_authenticated_client()
        account_id = config.DOCUSIGN_API_ACCOUNT_ID.strip()
        envelopes_api = EnvelopesApi(api_client)
        
        try:
            # 'combined' gets all documents as a single PDF
            document_data = envelopes_api.get_document(
                account_id=account_id, 
                envelope_id=envelope_id, 
                document_id='combined'
            )
            return document_data
        except Exception as e:
            print(f"Error getting envelope document: {str(e)}")
            raise e

docusign_service = DocuSignService()
