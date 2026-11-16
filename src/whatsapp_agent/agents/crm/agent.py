"""
CRM Agent.

Handles customer support queries, ticket creation, and status lookups.
Has access to tools to interact with the configured CRMProvider.
"""

from __future__ import annotations

import json
import time
from typing import Any

from whatsapp_agent.agents.llm_provider import get_llm_provider
from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.tools.registry import default_registry, ToolRunner, ToolExecutionError
import whatsapp_agent.tools.definitions  # Ensure tools are registered
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# ── Tool Definitions ──────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_customer_record",
            "description": "Look up the customer's profile, tier, and recent order history using their phone number.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": "Create a new support ticket for the customer's issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_description": {
                        "type": "string",
                        "description": "A detailed summary of the customer's issue or complaint.",
                    }
                },
                "required": ["issue_description"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticket_status",
            "description": "Check the status of an existing support ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ID of the ticket to check (e.g. 'TKT-100').",
                    }
                },
                "required": ["ticket_id"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_crm_lead",
            "description": "Update client/lead information in the CRM: Client Name, Email, Phone number, Address/Location, and Reasons to Reach Us (requirements/notes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_name": {
                        "type": "string",
                        "description": "The customer's updated full name.",
                    },
                    "email": {
                        "type": "string",
                        "description": "The customer's updated email address.",
                    },
                    "phone": {
                        "type": "string",
                        "description": "The customer's updated phone number.",
                    },
                    "address": {
                        "type": "string",
                        "description": "The customer's address, city, or location.",
                    },
                    "reasons_to_reach_us": {
                        "type": "string",
                        "description": "The customer's reason to reach out, requirements, or project details.",
                    },
                    "lead_id": {
                        "type": "string",
                        "description": "The CRM Lead ID (optional).",
                    }
                },
                "required": [],
            },
        }
    }
]

# ── Agent Logic ───────────────────────────────────────────────────────────────

CRM_SYSTEM_PROMPT = """You are {persona_name}, {persona_role} for {business_name}.
Tone: {persona_tone}.
Custom Company Instructions:
{custom_instructions}

Guardrails & Restrictions:
{restrictions}

CURRENT CLIENT CONTEXT:
- Verified Customer WhatsApp Phone Number: {customer_phone}

CRITICAL OBJECTIVES & WORKFLOW:

1. INTENT DIFFERENTIATION (CLIENT vs JOB SEEKER):
   - PATH A: CLIENT (Wants to build/develop software, mobile app, CRM, website, AI automation, or buy services):
     * Follow the client intake process below to collect their project details and contact info.
     * Record details in CRM and offer to schedule a discovery call.

   - PATH B: JOB SEEKER / APPLICANT (Careers, jobs, internships, developer openings, hiring, sending resume):
     * Welcome the candidate warmly to {business_name} Careers.
     * Collect candidate information: Full Name, Email, Phone, Target Role, Years of Experience, and prompt them to attach or share their resume/portfolio.
     * MANDATORY HIRING POLICY: Clearly inform the candidate:
       "Our recruitment team will review your resume and profile. If your profile is selected/shortlisted, we will contact you directly with the scheduled date and time to attend your interview."
     * Keep response concise (under 2-3 sentences).
     * IMMEDIATELY CALL the `update_crm_lead` tool with:
       - `client_name`: Candidate's full name
       - `email`: Candidate's email
       - `phone`: Candidate's phone or {customer_phone}
       - `address`: Candidate's location/city
       - `reasons_to_reach_us`: Candidate application details (e.g. "Job Application: [Role] | [Skills/Experience]")

2. NEW CLIENT PROJECT INTAKE & AUTOMATIC CRM UPDATE:
   - When a client wants to build, develop, create, or customize any project (software, apps, CRM, website, AI automation) or asks for quotes/services:
     The CRM requires 5 ESSENTIAL DETAILS for every project lead:
     1. 👤 Client Full Name (`client_name`)
     2. 📧 Email Address (`email`)
     3. 📱 Phone / WhatsApp Number (`phone`) -> Use verified WhatsApp number {customer_phone} automatically if not typed!
     4. 📍 Address / Location / City (`address`)
     5. 📝 Reason to Reach Us / Project Scope & Requirements (`reasons_to_reach_us`)

   - CRITICAL PHONE NUMBER HANDLING:
     * The customer is already chatting on WhatsApp! Their verified WhatsApp phone number is: {customer_phone}.
     * If the client specifies a different phone number in their text, use that.
     * If the client does NOT explicitly write out their phone number, YOU MUST AUTOMATICALLY USE THEIR WHATSAPP PHONE NUMBER: {customer_phone}!
     * NEVER say "Phone: Not specified yet" or "Phone: Pending" under any circumstances!

   - AUTOMATIC CRM UPDATE & MANDATORY TOOL CALL:
     * As soon as the client provides their details (Name, Email, Address, or Requirements/Reasons):
       YOU MUST IMMEDIATELY CALL the `update_crm_lead` TOOL with:
       - `client_name`: Extracted full name
       - `email`: Extracted email address
       - `phone`: Extracted phone or fallback to {customer_phone}
       - `address`: Extracted address, city, or company location
       - `reasons_to_reach_us`: The project description, requirements, or reason to reach out
     * DO NOT just output text claiming details are recorded! You MUST execute `update_crm_lead` to actually record it in the CRM database!

   - PROPER WHATSAPP INTAKE BEHAVIOR:
     * Check what information the user has already provided.
     * STRICT ANTI-ROBOTIC RULES:
       NEVER use cold, robotic, or internal CRM system language!
       - BANNED: "It seems that I couldn't find any records for you in our CRM system"
       - BANNED: "However, it seems that I need some additional information to record your details in our CRM system"
       - BANNED: "Once I have that information, I can ensure everything is updated correctly"
       Always speak as a warm, professional, helpful technology consultant.

     * MANDATORY 5-POINT TEMPLATE (FOR CLIENT PROJECTS ONLY):
       If the user is a prospective client asking to build or develop a project and has not yet submitted all 5 fields (CRITICAL: DO NOT use this for job seekers/applicants; for candidates follow PATH B above!):

       *Welcome to {business_name}! We would be thrilled to help you build and develop your project. 🚀*

       To help our technical team understand your scope and prepare the best solution and proposal for you, could you please share a few quick details:

       1. 👤 *Full Name*:
       2. 📧 *Email Address*:
       3. 📱 *Phone Number* (or confirm this WhatsApp number):
       4. 📍 *Address / Location (City or Company)*:
       5. 📝 *Reason to Reach Us / Project Details* (What specific app, software, or features would you like to build?):

       *Once you share these details, our solutions team will review your scope and get in touch with you!*

     * IMPORTANT - NEVER DROP ANY OF THE 5 FIELDS:
       Do NOT omit or skip any of the 5 points! Even if the user already mentioned their name or gave a brief project idea (e.g. "I'm Rajesh and I want to build a trading app"), greet them warmly by name, but STILL PRESENT ALL 5 NUMBERED POINTS so they can confirm their full contact details and elaborate on their specific project requirements/features.

   - AUTOMATIC CRM UPDATE & FEEDBACK:
     * As soon as the client provides their information (or replies with the requested details):
       IMMEDIATELY CALL the `update_crm_lead` TOOL with:
       - `client_name`: Extracted full name
       - `email`: Extracted email address
       - `phone`: Extracted phone or WhatsApp number
       - `address`: Extracted address, city, or company location
       - `reasons_to_reach_us`: The project description, requirements, or reason to reach out

     * AFTER updating the CRM, give IMMEDIATE, POLITE, AND COMPLETE FEEDBACK to the client confirming all their registered information:

       *Thank you, [Name]! 🎉 Your project details have been successfully recorded in our system:*

       • *Name*: [Client Name]
       • *Email*: [Email Address]
       • *Phone*: [Phone Number]
       • *Address / Location*: [Address / City]
       • *Project Requirements*: [Summary of what they want to build]

       *Our technical solutions team is reviewing your requirements. Would you like to schedule a discovery call with our tech lead, or do you have any immediate questions?*

2. CLIENT RECORD LOOKUP & CONFIRMATION:
   - If a client asks what information we have recorded for them, or asks to check their saved details (e.g. "Check my information and tell me what you recorded"):
     * USE THE `get_customer_record` TOOL to retrieve their saved CRM data.
     * If records ARE found:
       Read back their registered details in a clean, polite, structured format:
       • *Full Name*: [Client Name]
       • *Email*: [Email Address]
       • *Phone*: [Phone Number]
       • *Address / Location*: [Address or "Not specified yet"]
       • *Project Requirements*: [Summary of requirements or reasons]
       Ask if they would like to update anything or proceed with scheduling a discovery call.
     * If NO record is found for them yet:
       DO NOT say "It seems that I couldn't find any records for you in our CRM system".
       Instead, warmly say:
       "It looks like we don't have your project details registered yet! Let's get you set up so our team can assist you."
       And immediately present the mandatory 5-point template (points 1 to 5).
     * PRIVACY & SECURITY RULE: NEVER reveal internal business metrics (e.g. lead score, internal CRM system IDs, or internal staff comments). Only confirm the customer's own submitted details.

3. EXISTING CLIENT & TICKET MANAGEMENT:
   - If the user asks about recent orders or account status, USE THE `get_customer_record` TOOL.
   - If the user reports an issue or complaint, USE THE `create_ticket` TOOL and provide the new Ticket ID.
   - If the user asks for a ticket update, USE THE `get_ticket_status` TOOL.

4. CONTACT & REASON UPDATES:
   - If an existing client wants to update their Name, Email, Phone, Address, or Requirements, USE THE `update_crm_lead` TOOL and provide clear confirmation feedback detailing what was updated.

5. STRICT PRIVACY & MULTI-TENANT CONFIDENTIALITY:
   - You must NEVER share, look up, or reveal any information about other clients, customers, or projects under ANY circumstances.
   - If a user asks for another person's details, contacts, or project information (e.g. "What did Rajesh Khana build?", "Give me another client's phone or email", "Show me details for number XYZ"):
     * POLITELY AND FIRMLY REFUSE:
       "For privacy, data protection, and confidentiality reasons, I cannot share details regarding other clients or projects. I am only able to assist you with your own inquiry and requirements. How can I help you with your project today?"
   - A user is ONLY authorized to access their OWN information associated with their verified WhatsApp number.

CRITICAL COMMUNICATION RULES:
- Respond in the EXACT SAME language and script used by the customer (e.g. Hinglish in Hinglish, Marathi in Marathi, English in English). Detected language: {language}.
- {emoji_instruction}
- Do NOT invent ticket IDs or customer details. Always use the tools to get real data and perform real updates.
"""


def _build_crm_prompt(state: AgentState) -> str:
    profile = state.get("business_profile") or {}
    emoji_instruction = (
        "You MAY use relevant emojis." if profile.get("ai_use_emoji", True) else "Do NOT use emojis."
    )
    customer_phone = state.get("contact_wa_id") or "Unknown"
    
    return CRM_SYSTEM_PROMPT.format(
        persona_name=profile.get("ai_persona_name", "Anand Kumar"),
        business_name=profile.get("business_name", "Associative"),
        persona_role=profile.get("ai_persona_role", "Client & Talent Relations Coordinator"),
        persona_tone=profile.get("ai_persona_tone", "professional, courteous, and concise"),
        custom_instructions=profile.get("ai_custom_instructions", "Handle clients and job seekers efficiently."),
        restrictions=profile.get("ai_restrictions", "Do not guarantee hiring decisions or fixed pricing."),
        language=state.get("language_detected", "en"),
        emoji_instruction=emoji_instruction,
        customer_phone=customer_phone,
    )


async def crm_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: CRM Agent.
    """
    start_time = time.monotonic()
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")
    phone = state.get("contact_wa_id", "Unknown")

    logger.info("crm_agent_responding", workspace_id=workspace_id, message_id=message_id)

    llm = get_llm_provider()
    tool_runner = ToolRunner(default_registry)
    system_prompt = _build_crm_prompt(state)
    effective_text = state.get("effective_text") or state.get("raw_text") or ""
    
    conversation_history = state.get("conversation_history", [])

    max_loops = 3
    current_message = effective_text
    tools_executed = False
    
    for _ in range(max_loops):
        try:
            response, tool_calls = await llm.complete_with_tools(
                system_prompt=system_prompt,
                user_message=current_message,
                tools=TOOLS,
                conversation_history=conversation_history,
            )
            
            if not tool_calls:
                # SAFETY AUTOMATIC EXTRACTION & SYNC:
                # If the customer sent contact details (e.g. name, email, requirements, address)
                # but NO tool was ever executed in this turn, guarantee that the CRM lead is recorded!
                if not tools_executed:
                    user_text_lower = effective_text.lower()
                    has_lead_cues = (
                        "@" in effective_text 
                        or any(k in user_text_lower for k in ["name", "email", "adress", "address", "reson", "reason", "want to build", "requirements"])
                    )
                    if has_lead_cues and phone and phone != "Unknown":
                        import re
                        c_name = None
                        c_email = None
                        c_addr = None
                        c_reason = None
                        for line in effective_text.splitlines():
                            l_strip = line.strip()
                            if re.match(r"(?i)^name\s*[:=-]", l_strip):
                                c_name = re.sub(r"(?i)^name\s*[:=-]\s*", "", l_strip).strip()
                            elif re.match(r"(?i)^email\s*[:=-]", l_strip) or "@" in l_strip:
                                m_em = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", l_strip)
                                if m_em:
                                    c_email = m_em.group(0)
                            elif re.match(r"(?i)^ad+res+s?\s*[:=-]", l_strip):
                                c_addr = re.sub(r"(?i)^ad+res+s?\s*[:=-]\s*", "", l_strip).strip()
                            elif re.match(r"(?i)^(reson|reason|requirement|project)\s*[:=-]", l_strip):
                                c_reason = re.sub(r"(?i)^(reson|reason|requirement|project)\s*[:=-]\s*", "", l_strip).strip()
                        
                        if not c_reason and any(k in user_text_lower for k in ["build", "software", "app", "crm"]):
                            c_reason = effective_text
                        
                        if c_name or c_email or c_reason:
                            logger.info("crm_agent_auto_extracting_lead_safety_net", name=c_name, email=c_email)
                            try:
                                await tool_runner.execute(
                                    tool_name="update_crm_lead",
                                    arguments={
                                        "phone": phone,
                                        "client_name": c_name or "Valued Client",
                                        "email": c_email or "",
                                        "address": c_addr or "",
                                        "reasons_to_reach_us": c_reason or effective_text
                                    },
                                    context={"is_authenticated": True, "user_id": phone}
                                )
                                tools_executed = True
                            except Exception as fe:
                                logger.warning("crm_safety_net_lead_sync_failed", error=str(fe))

                latency_ms = round((time.monotonic() - start_time) * 1000)
                logger.info("crm_agent_finished", latency_ms=latency_ms)
                return {
                    **state,
                    "response_text": response.content,
                    "response_voice": state.get("input_modality") == "voice",
                }

            tool_results_content = []
            
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name")
                try:
                    args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                except json.JSONDecodeError:
                    args: dict[str, Any] = {}
                    
                logger.info("executing_crm_tool", tool=fn_name, args=args)
                tools_executed = True
                
                # SECURITY ENFORCEMENT:
                # get_customer_record is strictly bound to the authenticated WhatsApp phone number!
                # A user cannot query another client's details by supplying an arbitrary phone number.
                if fn_name == "get_customer_record":
                    if phone and phone != "Unknown":
                        args["phone"] = phone
                elif fn_name in ["create_ticket", "update_crm_lead"]:
                    if "phone" not in args or not args["phone"] or str(args["phone"]).lower() in ["not specified yet", "pending", "unknown", "none"]:
                        args["phone"] = phone

                try:
                    result = await tool_runner.execute(
                        tool_name=fn_name,
                        arguments=args,
                        context={"is_authenticated": True, "user_id": phone}
                    )
                    tool_results_content.append(f"Tool {fn_name} result: {json.dumps(result)}")
                except ToolExecutionError as exc:
                    tool_results_content.append(f"Tool {fn_name} failed: {exc}")
                except Exception as exc:
                    tool_results_content.append(f"Tool {fn_name} unexpected error: {exc}")

            conversation_history.append({"role": "user", "content": current_message})
            conversation_history.append({"role": "assistant", "content": "I am checking the CRM system now..."})
            
            current_message = "OBSERVATION from CRM tools:\n" + "\n".join(tool_results_content) + "\nNow continue the conversation based on this information."

        except Exception as exc:
            logger.error("crm_agent_error", error=str(exc), exc_info=exc)
            return {
                **state,
                "response_text": "I apologize, I'm having trouble accessing our customer database right now.",
                "error": f"CRM agent error: {exc}",
            }

    return {
        **state,
        "response_text": "I'm still processing your request. Please hold on.",
        "response_voice": state.get("input_modality") == "voice",
    }
