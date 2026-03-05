import logging
import os
import time
import json
from typing import Dict, Any

# Attempt to import LLM libraries
try:
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

class Extractor:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.use_llm = HAS_LLM and bool(self.api_key)
        
        if self.use_llm:
            try:
                self.client = Groq(api_key=self.api_key)
                self.model = 'llama-3.1-8b-instant' # Fast, free, robust for JSON extraction
                logging.info("Extractor initialized WITH Groq LLM.")
            except Exception as e:
                logging.error(f"Failed to initialize Groq Client: {e}")
                self.use_llm = False
        else:
            logging.warning("Extractor initialized WITHOUT Groq API Key. Using fallback rule-based extraction.")

    def _extract_via_llm(self, text: str, prompt: str, schema: dict, fallback_data: Dict, retries: int = 3) -> Dict:
        """Single fast LLM call. Contacts pre-injected into prompt to prevent hallucination."""
        for attempt in range(retries):
            try:
                system_instruction = prompt + f"\nYou must reply ONLY with valid JSON matching this schema exactly:\n{json.dumps(schema)}"
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": f"TRANSCRIPT/DATA:\n{text[:10000]}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                return json.loads(response.choices[0].message.content.strip())
            except Exception as e:
                logging.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if "rate limit" in str(e).lower() or "429" in str(e) or "413" in str(e):
                    logging.warning("Rate limit hit. Sleeping for 15 seconds.")
                    time.sleep(15)
                else:
                    time.sleep(2)
        logging.error("All LLM attempts failed. Falling back to rule-based logic.")
        return fallback_data

    def extract_demo_memo(self, text: str, account_id: str) -> Dict[str, Any]:
        """
        Parses text to extract structured business configuration information.
        Falls back to pure Python rules if it fails.
        """
        # --- 1. Define the Fallback Logic (used if LLM fails or no API key is present) ---
        fallback_memo = {
            "account_id": account_id,
            "company_name": "Unknown",
            "contact_phone": "Unknown",
            "contact_email": "Unknown",
            "business_hours": {"days": "Unknown", "start": "Unknown", "end": "Unknown", "timezone": "Unknown"},
            "office_address": "Unknown",
            "services_supported": [],
            "emergency_definition": ["Unknown"],
            "emergency_routing_rules": ["Unknown"],
            "non_emergency_routing_rules": "Unknown",
            "call_transfer_rules": "Unknown",
            "integration_constraints": "Unknown",
            "after_hours_flow_summary": "Unknown",
            "office_hours_flow_summary": "Unknown",
            "questions_or_unknowns": ["Business hours", "Address", "Exact routing strategy"],
            "notes": ""
        }
        
        import re
        text_lower = text.lower()
        resolved_demo = []

        # Regex: extract emails
        demo_emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
        if demo_emails:
            fallback_memo["contact_email"] = demo_emails[0]
            resolved_demo.append("contact email")

        # Regex: extract phone numbers (line by line)
        for _dl in text.splitlines():
            _phones = re.findall(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}', _dl)
            if _phones:
                fallback_memo["contact_phone"] = _phones[0].strip()
                resolved_demo.append("contact phone")
                break

        # Regex: extract business hours
        _hrs = re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[\s\w\-]+(to|through|-)[\s\w\-]+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', text_lower)
        _times = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))[\s\w\-]+(to|through|-)[\s\w\-]+(\d{1,2}(?::\d{2})?\s*(?:am|pm))', text_lower)
        _tz = re.search(r'\b(est|pst|mst|cst|gmt|utc|eastern|pacific|mountain|central)\b', text_lower)
        if _hrs:
            fallback_memo["business_hours"]["days"] = _hrs.group(0).title()
            resolved_demo.append("business hours days")
        if _times:
            fallback_memo["business_hours"]["start"] = _times.group(1).upper()
            fallback_memo["business_hours"]["end"] = _times.group(3).upper()
            resolved_demo.append("business hours times")
        if _tz:
            fallback_memo["business_hours"]["timezone"] = _tz.group(1).upper()
            resolved_demo.append("timezone")

        # Keyword layer: detect generic services and routing from transcript vocabulary
        # Company name: require at least 2+ capitalized words followed by a business-type suffix
        company_match = re.search(
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+\s+(?:Solutions|Services|Group|Inc|LLC|Corp|Electric|Electrical|Plumbing|HVAC|Fire|Alarm|Sprinkler|Protection))\b',
            text
        )
        if company_match and fallback_memo.get("company_name") == "Unknown":
            fallback_memo["company_name"] = company_match.group(1).strip()

        # Services: only detect if keyword appears in a job/trade context, not just anywhere
        # Use narrower list — only explicit trade services, not generic words like 'maintenance'
        service_keywords = ['electrical', 'plumbing', 'hvac', 'fire protection', 'sprinkler system',
                            'alarm system', 'residential wiring', 'commercial wiring',
                            'pressure washing', 'roofing', 'landscaping', 'cleaning',
                            'pest control', 'contracting', 'hvac/r', 'remodeling']
        detected_services = [kw.title() for kw in service_keywords if kw in text_lower]
        if detected_services:
            fallback_memo["services_supported"] = detected_services

        # Emergency routing: if transcript mentions name + "on call" or "call [name]"
        oncall_match = re.search(r'call\s+([A-Z][a-z]+)\s+(?:personally|directly|first|for emergencies)', text)
        if oncall_match:
            fallback_memo["emergency_routing_rules"] = [f"Call {oncall_match.group(1)} personally (on call for emergencies)"]

        # Non-emergency / office-hours: require at least 2 of these words together (not just 'job' alone)
        routing_words = ['schedule', 'qualify', 'appointment', 'receptionist']
        if sum(1 for w in routing_words if w in text_lower) >= 2:
            fallback_memo["non_emergency_routing_rules"] = "AI virtual receptionist qualifies jobs and schedules appointments."
            fallback_memo["office_hours_flow_summary"] = "Filter and qualify calls during business hours, schedule appointments."

        # After-hours: require 'after hours' or 'on call' — not just 'emergency' alone
        if 'after hours' in text_lower or 'after-hours' in text_lower or 'on call' in text_lower:
            fallback_memo["after_hours_flow_summary"] = "Route emergency calls to on-call staff after hours."

        # CRM / integration detection — specific tool names, fine as-is
        crm_keys = ['jobber', 'servicetrade', 'salesforce', 'hubspot', 'zoho', 'freshdesk', 'zendesk', 'quickbooks']
        found_crm = [k for k in crm_keys if k in text_lower]
        if found_crm:
            fallback_memo["integration_constraints"] = f"CRM/tool mentioned: {', '.join(found_crm)}."

        # Clean questions_or_unknowns based on what was resolved
        fallback_memo["questions_or_unknowns"] = [
            q for q in fallback_memo["questions_or_unknowns"]
            if not any(r.lower() in q.lower() for r in resolved_demo)
        ]


            
        # --- 2. Attempt LLM Extraction ---
        if self.use_llm:
            # Pre-extract ALL phones and emails from the FULL text using regex,
            # then inject as VERIFIED CONTACT DATA into the prompt.
            # This way the LLM gets real contacts regardless of where in the text they appear.
            all_phones = list(dict.fromkeys(re.findall(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', text)))
            all_emails = list(dict.fromkeys(re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)))
            # Filter out Clara AI / demo platform emails
            client_emails = [e for e in all_emails if 'clara.ai' not in e.lower() and 'claraai' not in e.lower()]
            contact_hint = ""
            if all_phones or client_emails:
                contact_hint = f"""
            VERIFIED CONTACT DATA (extracted from the full transcript — use these exact values):
            - Phone numbers found: {all_phones if all_phones else 'None found'}
            - Email addresses found: {client_emails if client_emails else 'None found'}
            Use the FIRST phone as contact_phone and FIRST email as contact_email. Do NOT invent any other phone or email.
            """

            prompt = f"""
            You are an elite AI Configuration Architect. Your task is to analyze the following raw conversation transcript and construct a highly accurate, comprehensive Account Memo for the CLIENT BUSINESS being onboarded.
            {contact_hint}
            CRITICAL INSTRUCTIONS:
            1. EXHAUSTIVE EXTRACTION: Read the transcript carefully. Do not miss ANY explicit rules, services, integration limits, or constraints mentioned. If mentioned, it MUST be logged.
            2. ZERO HALLUCINATION (CRITICAL): If a piece of information is missing entirely, YOU MUST USE EXACTLY the string "Unknown". Do NOT invent or assume facts. Do NOT make negative inferences — if call transfer rules are not mentioned, the value is "Unknown", NOT "Calls are not transferred to anyone". Only state what was EXPLICITLY said or discussed.
            3. NO COMPANY NAME FROM EMAIL DOMAINS (CRITICAL): Do NOT derive company_name from email addresses or their domains. Only use a company name that was explicitly spoken or written as a business name in the conversation. If no company name is stated, use "Unknown".
            4. IGNORE CLARA AI BRANDING: "Clara" is the name of the AI PRODUCT/TOOL being demonstrated — it is NOT the client company. Do NOT use "Clara AI" or any Clara-related branding as the company_name, contact_email, or contact_phone. Extract only the actual client business details.
            5. PHONE AND EMAIL: Use ONLY the VERIFIED CONTACT DATA above. Do NOT invent or guess any phone/email not listed there.
            6. SERVICES (CRITICAL): `services_supported` must ONLY contain actual trade/industry services the business offers (e.g. "Electrical", "Plumbing", "HVAC"). Do NOT list software tools (Jobber, CRM, QuickBooks) here — those belong in `integration_constraints`. If no trade services are explicitly named, use ["Unknown"].
            7. DETAILED ROUTING: Pay extremely close attention to how emergencies vs. non-emergencies are handled, as well as VIP callers or personal numbers.
            8. ROBUST SUMMARY: Ensure the `notes` field contains every tangential but important operational fact discussed.
            9. FLOW SUMMARY FIELDS (IMPORTANT): For `after_hours_flow_summary` and `office_hours_flow_summary`, do NOT default to "Unknown" just because a formal policy was not stated. If the transcript MENTIONS OR DISCUSSES on-call staff, after-hours handling, scheduling, appointments, or business hours flow — even as a question, example, or partial answer — SUMMARIZE what was discussed. Only use "Unknown" if the topic is never mentioned at all in the transcript.
            """
            
            schema = {
                "type": "OBJECT",
                "properties": {
                    "account_id": {"type": "STRING"},
                    "company_name": {"type": "STRING"},
                    "contact_phone": {"type": "STRING"},
                    "contact_email": {"type": "STRING"},
                    "business_hours": {
                        "type": "OBJECT",
                        "properties": {
                            "days": {"type": "STRING"},
                            "start": {"type": "STRING"},
                            "end": {"type": "STRING"},
                            "timezone": {"type": "STRING"}
                        }
                    },
                    "office_address": {"type": "STRING"},
                    "services_supported": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "emergency_definition": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "emergency_routing_rules": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "non_emergency_routing_rules": {"type": "STRING"},
                    "call_transfer_rules": {"type": "STRING"},
                    "integration_constraints": {"type": "STRING"},
                    "after_hours_flow_summary": {"type": "STRING"},
                    "office_hours_flow_summary": {"type": "STRING"},
                    "questions_or_unknowns": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "notes": {"type": "STRING"}
                },
                "required": [
                    "account_id", "company_name", "contact_phone", "contact_email", "business_hours", "office_address",
                    "services_supported", "emergency_definition", "emergency_routing_rules",
                    "non_emergency_routing_rules", "call_transfer_rules", "integration_constraints",
                    "after_hours_flow_summary", "office_hours_flow_summary", "questions_or_unknowns"
                ]
            }
            
            llm_result = self._extract_via_llm(text, prompt, schema, fallback_memo)

            # Post-LLM patch: for phone/email, ALWAYS prefer the regex-extracted value
            # if regex found one. Regex literally cannot hallucinate — it only returns
            # strings physically present in the full transcript. The LLM may hallucinate
            # plausible-looking but wrong emails/phones from partial context.
            if fallback_memo.get('contact_phone') not in ('Unknown', '', None):
                llm_result['contact_phone'] = fallback_memo['contact_phone']
                logging.info("Post-patch: Using regex-extracted phone (more reliable than LLM).")
            if fallback_memo.get('contact_email') not in ('Unknown', '', None):
                llm_result['contact_email'] = fallback_memo['contact_email']
                logging.info("Post-patch: Using regex-extracted email (more reliable than LLM).")

            return llm_result
            
        return fallback_memo


    def extract_onboarding_updates(self, text: str, v1_memo: Dict[str, Any]) -> Dict[str, Any]:
        """
        Loads existing v1 account memo and parses onboarding transcript to update fields.
        Falls back to pure Python rules if it fails.
        """
        # --- 1. Define the Fallback Logic (comprehensive regex extractor) ---
        import re
        v2_memo_fallback = json.loads(json.dumps(v1_memo)) # Deep copy of v1
        text_lower = text.lower()
        resolved = []
        extra_notes = []

        # 1. Extract all email addresses
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
        if emails:
            v2_memo_fallback["contact_email"] = emails[0]
            if len(emails) > 1:
                extra_notes.append(f"Additional emails: {', '.join(emails[1:])}") 
            resolved.append("contact email")
            logging.info(f"Fallback: Extracted emails: {emails}")

        # 2. Extract phone numbers (line by line to avoid timestamp bleed)
        for _line in text.splitlines():
            line_phones = re.findall(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}', _line)
            if line_phones:
                v2_memo_fallback["contact_phone"] = line_phones[0].strip()
                resolved.append("contact phone")
                logging.info(f"Fallback: Extracted phone: {line_phones[0]}")
                break

        # 3. Extract URLs/websites
        urls = re.findall(r'https?://[^\s]+|www\.[^\s]+', text)
        if urls:
            extra_notes.append(f"Website/URL mentioned: {urls[0]}")
            logging.info(f"Fallback: Extracted URL: {urls[0]}")

        # 4. Extract business hours patterns (e.g. '8 AM to 5 PM', 'Monday to Friday')
        hours_match = re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[\s\w\-]+(to|through|–|-)[\s\w\-]+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', text_lower)
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))[\s\w\-]+(to|through|–|-)[\s\w\-]+(\d{1,2}(?::\d{2})?\s*(?:am|pm))', text_lower)
        timezone_match = re.search(r'\b(est|pst|mst|cst|gmt|utc|eastern|pacific|mountain|central|mountain time)\b', text_lower)
        if hours_match and v2_memo_fallback.get('business_hours', {}).get('days') == 'Unknown':
            v2_memo_fallback['business_hours']['days'] = hours_match.group(0).title()
            resolved.append("business hours days")
        if time_match and v2_memo_fallback.get('business_hours', {}).get('start') == 'Unknown':
            v2_memo_fallback['business_hours']['start'] = time_match.group(1).upper()
            v2_memo_fallback['business_hours']['end'] = time_match.group(3).upper()
            resolved.append("business hours times")
        if timezone_match and v2_memo_fallback.get('business_hours', {}).get('timezone') == 'Unknown':
            v2_memo_fallback['business_hours']['timezone'] = timezone_match.group(1).upper()
            resolved.append("timezone")

        # 5. Extract CRM/software/tool mentions
        crm_keywords = ['jobber', 'servicetrade', 'salesforce', 'hubspot', 'zoho', 'freshdesk', 'zendesk', 'slack', 'teams', 'quickbooks']
        found_crms = [kw for kw in crm_keywords if kw in text_lower]
        if found_crms and v2_memo_fallback.get('integration_constraints') in ('Unknown', '', None):
            v2_memo_fallback['integration_constraints'] = f"CRM/tools mentioned: {', '.join(found_crms)}"
            resolved.append("integration")

        # 6. Extract company/contact name from "From X : <content>" chat format
        chat_lines = re.findall(r'From\s+\w+\s*:\s*(.+)', text)
        for _chat_line in chat_lines:
            _chat_line = _chat_line.strip()
            if _chat_line and '@' not in _chat_line and not re.search(r'\d{3,}', _chat_line) and 1 < len(_chat_line.split()) <= 6:
                if v2_memo_fallback.get("company_name") in ("Unknown", "", None):
                    v2_memo_fallback["company_name"] = _chat_line
                    resolved.append("company name")
                    break

        # 7. Merge any extra notes found
        if extra_notes:
            existing = v2_memo_fallback.get("notes", "")
            v2_memo_fallback["notes"] = (existing + " " + " | ".join(extra_notes)).strip()

        # 8. Remove resolved items from questions_or_unknowns
        existing_unknowns = v2_memo_fallback.get("questions_or_unknowns", [])
        v2_memo_fallback["questions_or_unknowns"] = [
            q for q in existing_unknowns
            if not any(r.lower() in q.lower() for r in resolved)
        ]


        # --- 2. Attempt LLM Extraction ---
        if self.use_llm:
            # Pre-extract ALL phones and emails from the full onboarding text
            ob_phones = list(dict.fromkeys(re.findall(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', text)))
            ob_all_emails = list(dict.fromkeys(re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)))
            ob_client_emails = [e for e in ob_all_emails if 'clara.ai' not in e.lower()]
            ob_contact_hint = ""
            if ob_phones or ob_client_emails:
                ob_contact_hint = f"""
            VERIFIED CONTACT DATA (pre-extracted from the full transcript — use these EXACT values):
            - Phone numbers: {ob_phones if ob_phones else 'None found'}
            - Email addresses: {ob_client_emails if ob_client_emails else 'None found'}
            Use the FIRST phone as contact_phone. If V1 already has a phone and transcript adds another, keep the transcript phone as it is more recent.
            Use the FIRST email as contact_email. Log any additional emails in notes as "Additional emails: ...".
            Do NOT invent any contact info not listed above.
            """

            prompt = f"""
            You are a meticulous Data Integration Expert.
            You are given an existing Account Memo (v1) and a new follow-up Onboarding Call transcript.
            {ob_contact_hint}
            CRITICAL INSTRUCTIONS:
            1. EXHAUSTIVE EXTRACTION: Scan EVERY line. Extract ALL of the following if present:
               - Emails, phone numbers, URLs/websites
               - Company name, contact person names
               - Business hours (days, start time, end time, timezone)
               - Physical address or office location
               - CRM/software/tool names (Jobber, ServiceTrade, Salesforce, etc.)
               - Emergency definition, routing rules, transfer rules, integration constraints
               - After-hours flow, office hours flow
               - Any special operational rules, constraints, or exceptions
            2. RESOLVE UNKNOWNS: Update EVERY "Unknown" field that the transcript contains information for. Clear `questions_or_unknowns` items that are now answered.
            3. ZERO HALLUCINATION (CRITICAL): If the transcript does NOT explicitly state a value, it stays "Unknown". NEVER invent business hours, addresses, or any other fact. DO NOT make negative inferences — if something is not mentioned, the value is "Unknown", NOT "X is not Y" or "X are not explicitly handled".
            4. NEVER DROP FIELDS (CRITICAL): Do NOT set a field BACK to "Unknown" if V1 already had a real value AND the transcript does not contradict it. However, if the transcript explicitly provides NEW or BETTER information for a field (even company_name), use the transcript's version — that is an UPDATE, not a drop.
            5. MERGE SAFELY: The new transcript SUPPLEMENTS V1. If V1 has routing rules, CRM, flow summaries etc. and the transcript does not contradict them, carry them forward.
            6. PHONE AND EMAIL: Use ONLY the VERIFIED CONTACT DATA above. Do NOT invent or guess any contact not listed there.
            7. NO COMPANY NAME FROM EMAIL DOMAINS (CRITICAL): Do NOT derive company_name from email addresses or domain names. Only use an explicitly stated business name from the transcript.
            
            Current V1 Profile:
            {json.dumps(v1_memo, indent=2)}
            
            Return the full, updated JSON schema matching the exact structure from V1.
            """
            
            schema = {
                "type": "OBJECT",
                "properties": {
                    "account_id": {"type": "STRING"},
                    "company_name": {"type": "STRING"},
                    "contact_phone": {"type": "STRING"},
                    "contact_email": {"type": "STRING"},
                    "business_hours": {
                        "type": "OBJECT",
                        "properties": {
                            "days": {"type": "STRING"},
                            "start": {"type": "STRING"},
                            "end": {"type": "STRING"},
                            "timezone": {"type": "STRING"}
                        }
                    },
                    "office_address": {"type": "STRING"},
                    "services_supported": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "emergency_definition": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "emergency_routing_rules": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "non_emergency_routing_rules": {"type": "STRING"},
                    "call_transfer_rules": {"type": "STRING"},
                    "integration_constraints": {"type": "STRING"},
                    "after_hours_flow_summary": {"type": "STRING"},
                    "office_hours_flow_summary": {"type": "STRING"},
                    "questions_or_unknowns": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "notes": {"type": "STRING"}
                },
                "required": [
                    "account_id", "company_name", "contact_phone", "contact_email", "business_hours", "office_address",
                    "services_supported", "emergency_definition", "emergency_routing_rules",
                    "non_emergency_routing_rules", "call_transfer_rules", "integration_constraints",
                    "after_hours_flow_summary", "office_hours_flow_summary", "questions_or_unknowns"
                ]
            }
            
            llm_result = self._extract_via_llm(text, prompt, schema, v2_memo_fallback)

            # Post-LLM patch: for phone/email, ALWAYS prefer the regex-extracted value
            # if regex found one. Regex literally cannot hallucinate.
            if v2_memo_fallback.get('contact_phone') not in ('Unknown', '', None):
                llm_result['contact_phone'] = v2_memo_fallback['contact_phone']
                logging.info("Post-patch: Using regex-extracted phone in onboarding.")
            if v2_memo_fallback.get('contact_email') not in ('Unknown', '', None):
                llm_result['contact_email'] = v2_memo_fallback['contact_email']
                logging.info("Post-patch: Using regex-extracted email in onboarding.")

            return llm_result

        return v2_memo_fallback

    def extract_agent_spec(self, memo: Dict[str, Any], version: str) -> Dict[str, Any]:
        """
        Parses Account Memo to build the Agent Spec.
        Falls back to pure Python rules if it fails.
        """
        # --- 1. Define the Fallback Logic (scripted two-flow prompt) ---
        _company = memo.get('company_name', 'Unknown')
        _biz_hours = memo.get('business_hours', {})
        _biz_hours_str = f"{_biz_hours.get('days','TBD')}, {_biz_hours.get('start','TBD')} to {_biz_hours.get('end','TBD')} {_biz_hours.get('timezone','')}".strip()
        _emergency_def = ', '.join(memo.get('emergency_definition', ['TBD']))
        _emergency_routing = ', '.join(memo.get('emergency_routing_rules', ['TBD']))
        _non_emergency_routing = memo.get('non_emergency_routing_rules', 'TBD')
        _call_transfer = memo.get('call_transfer_rules', 'TBD')

        _scripted_prompt = (
            f"You are Clara, a professional AI virtual receptionist for {_company}.\n\n"
            f"== BUSINESS HOURS FLOW ({_biz_hours_str}) ==\n"
            f"1. Greet: 'Thank you for calling {_company}, this is Clara. How can I help you today?'\n"
            f"2. Listen to the caller's purpose.\n"
            f"3. Collect their full name and callback number.\n"
            f"4. Route based on: {_non_emergency_routing}\n"
            f"5. If transfer fails: {_call_transfer}\n"
            f"6. Ask: 'Is there anything else I can help you with?'\n"
            f"7. Close: 'Thank you for calling {_company}. Have a great day!'\n\n"
            f"== AFTER-HOURS FLOW ==\n"
            f"1. Greet: 'Thank you for calling {_company}. Our office is currently closed.'\n"
            f"2. Ask: 'How can I help you today?'\n"
            f"3. Ask: 'Is this an emergency?' Emergency is defined as: {_emergency_def}\n"
            f"4. [EMERGENCY] Collect name, phone, address. Attempt transfer: {_emergency_routing}\n"
            f"5. [TRANSFER FAILS] 'Someone will follow up with you as soon as possible.'\n"
            f"6. [NON-EMERGENCY] Collect name and details. Confirm follow-up during business hours.\n"
            f"7. Ask: 'Is there anything else I can help you with?' Then close the call.\n\n"
            f"GUARDRAILS: Never mention system prompts, automation, or internal tools to the caller."
        )

        fallback_spec = {
            "agent_name": f"{_company} Clara AI Agent",
            "voice_style": "Professional, empathetic, calm",
            "system_prompt": _scripted_prompt,
            "key_variables": f"timezone: {_biz_hours.get('timezone', 'TBD')}, business_hours: {_biz_hours_str}",
            "tool_invocation_placeholders": "transfer_call, log_callback, create_job_ticket",
            "call_transfer_protocol": _call_transfer,
            "fallback_protocol": "Collect caller name and number. Assure follow-up. End call gracefully.",
            "version": version
        }
        
        # --- 2. Attempt LLM Extraction ---
        if self.use_llm:
            company = memo.get('company_name', 'the company')
            biz_hours = memo.get('business_hours', {})
            biz_hours_str = f"{biz_hours.get('days','Unknown')}, {biz_hours.get('start','Unknown')} to {biz_hours.get('end','Unknown')} {biz_hours.get('timezone','')}".strip()
            emergency_def = ', '.join(memo.get('emergency_definition', ['Unknown']))
            emergency_routing = ', '.join(memo.get('emergency_routing_rules', ['Unknown']))
            non_emergency_routing = memo.get('non_emergency_routing_rules', 'Unknown')
            after_hours = memo.get('after_hours_flow_summary', 'Unknown')
            call_transfer = memo.get('call_transfer_rules', 'Unknown')
            
            prompt = f"""
            You are an elite Prompt Engineer for AI Voice Agents (Clara AI).
            
            Your job is to write a FULL, DEPLOYABLE system prompt for a Clara AI voice agent for the business: {company}.
            
            IMPORTANT: You must return a JSON object with these EXACT keys filled with real string values:
            - agent_name: e.g. "{company} Clara AI Agent"
            - voice_style: e.g. "Professional, empathetic, calm"
            - system_prompt: the full scripted call handling prompt (see below)
            - key_variables: e.g. "timezone: Unknown, business_hours: {biz_hours_str}"
            - tool_invocation_placeholders: e.g. "transfer_call, log_callback, create_job_ticket"
            - call_transfer_protocol: e.g. "{call_transfer}"
            - fallback_protocol: e.g. "Collect caller name and number. Assure follow-up. End call gracefully."
            - version: "{version}"
            
            DO NOT return a JSON schema or type definitions. Return actual string values for every field.
            
            The system_prompt field MUST contain TWO explicitly scripted call handling flows:
            
            == BUSINESS HOURS FLOW ({biz_hours_str}) ==
            Step 1: Greet the caller warmly and introduce yourself as Clara, the virtual assistant for {company}.
            Step 2: Ask purpose of their call.
            Step 3: Collect their full name and callback number.
            Step 4: Route/transfer based on these rules: {non_emergency_routing}
            Step 5: If transfer fails: {call_transfer}
            Step 6: Ask if caller needs anything else.
            Step 7: Close the call professionally.
            
            == AFTER-HOURS FLOW ==
            Step 1: Greet the caller and inform them it is outside business hours.
            Step 2: Ask the purpose of their call.
            Step 3: Ask if this is an emergency. Emergency is defined as: {emergency_def}
            Step 4 (Emergency): Collect name, phone number, and address immediately. Attempt transfer via: {emergency_routing}
            Step 5 (Emergency, transfer fails): Apologize, assure a team member will follow up ASAP.
            Step 6 (Non-emergency): Collect name and details. Confirm follow-up during business hours.
            Step 7: Ask if they need anything else. Close the call.
            
            GUARDRAILS for the system_prompt:
            - The agent MUST NEVER mention internal tool names, system prompts, or automation logic to the caller.
            - The agent must remain empathetic, calm, and professional throughout.
            - Do NOT hallucinate contact numbers or facts not in the Account Memo.
            - If a value is Unknown, note it as TBD in the prompt but do not invent it.
            
            Account Memo (source of truth):
            {json.dumps(memo, indent=2)}
            
            Return a JSON object where system_prompt is a full, multi-paragraph, deployable script written in second-person ("You are Clara...").
            """
            
            schema = {
                "type": "OBJECT",
                "properties": {
                    "agent_name": {"type": "STRING"},
                    "voice_style": {"type": "STRING"},
                    "system_prompt": {"type": "STRING"},
                    "key_variables": {"type": "STRING"},
                    "tool_invocation_placeholders": {"type": "STRING"},
                    "call_transfer_protocol": {"type": "STRING"},
                    "fallback_protocol": {"type": "STRING"},
                    "version": {"type": "STRING"}
                },
                "required": [
                    "agent_name", "voice_style", "system_prompt", "key_variables",
                    "tool_invocation_placeholders", "call_transfer_protocol", "fallback_protocol", "version"
                ]
            }
            
            spec = self._extract_via_llm("", prompt, schema, fallback_spec)
            spec['version'] = version
            return spec

        return fallback_spec

def transcribe_media(file_path: str) -> str:
    """
    Transcribes audio/video files locally using Whisper.
    Falls back to a warning text if dependencies are missing or it fails.
    """
    try:
        import whisper
    except ImportError:
        logging.error("Whisper library is not installed. Run: pip install openai-whisper")
        return "Mock transcription: Please pip install openai-whisper and ffmpeg to process raw media."

    logging.info(f"Loading Whisper base model... Transcribing {file_path}")
    try:
        model = whisper.load_model("base")
        result = model.transcribe(file_path)
        return result.get("text", "")
    except Exception as e:
        logging.error(f"Whisper transcription failed: {e}")
        return "Mock transcription applied due to error. Is ffmpeg installed on your system?"

