"""
sip_setup.py — شغّله مرة واحدة فقط لإعداد SIP Trunks + Dispatch Rules على LiveKit.

الاستخدام:
    pip install livekit-api
    python sip_setup.py

متغيرات البيئة المطلوبة (من .env.local أو export):
    LIVEKIT_URL
    LIVEKIT_API_KEY
    LIVEKIT_API_SECRET
    SIP_PROVIDER_NUMBER      — رقمك من Twilio (مثال: +966XXXXXXXXX)
    SIP_OUTBOUND_HOST        — Termination URI من Twilio (مثال: xxx.pstn.twilio.com)
    SIP_USERNAME             — username من Credential List في Twilio
    SIP_PASSWORD             — password من Credential List في Twilio
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import (
    CreateSIPInboundTrunkRequest,
    CreateSIPOutboundTrunkRequest,
    CreateSIPDispatchRuleRequest,
    CreateSIPParticipantRequest,
    SIPInboundTrunkInfo,
    SIPOutboundTrunkInfo,
    SIPDispatchRuleInfo,
    SIPDispatchRule,
    SIPDispatchRuleIndividual,
)
# from livekit.protocol.room import RoomConfiguration
from livekit.protocol.room import RoomConfiguration, RoomAgent
load_dotenv(".env.local")

# ── إعدادات LiveKit ──────────────────────────────────────────────────────────
LIVEKIT_URL    = os.environ["LIVEKIT_URL"]
API_KEY        = os.environ["LIVEKIT_API_KEY"]
API_SECRET     = os.environ["LIVEKIT_API_SECRET"]

# ── إعدادات SIP Provider (Twilio) ────────────────────────────────────────────
# رقمك من Twilio — ممكن أكتر من رقم
SIP_PROVIDER_NUMBERS = os.getenv("SIP_PROVIDER_NUMBERS", "").split(",")
SIP_PROVIDER_NUMBERS = [n.strip() for n in SIP_PROVIDER_NUMBERS if n.strip()]

SIP_OUTBOUND_HOST = os.getenv("SIP_OUTBOUND_HOST", "")   # xxx.pstn.twilio.com
SIP_USERNAME      = os.getenv("SIP_USERNAME", "")
SIP_PASSWORD      = os.getenv("SIP_PASSWORD", "")

# ── تعريف الأرقام والـ personas ───────────────────────────────────────────────
# كل رقم له persona مختلفة — عدّل حسب احتياجك
# مثال: [{"number": "+966XXXXXXXXX", "persona": "customer_service", "prefix": "cs-"}]
NUMBER_PERSONA_MAP = [
    {
        "number": SIP_PROVIDER_NUMBERS[0] if len(SIP_PROVIDER_NUMBERS) > 0 else "",
        "persona": "customer_service",
        "room_prefix": "cs-",
        "name": "خدمة العملاء",
    },
    # أضف أرقام إضافية هنا
    # {
    #     "number": SIP_PROVIDER_NUMBERS[1] if len(SIP_PROVIDER_NUMBERS) > 1 else "",
    #     "persona": "sales",
    #     "room_prefix": "sales-",
    #     "name": "المبيعات",
    # },
]


async def main() -> None:
    print("=" * 55)
    print("  SIP Setup — LiveKit Call Center")
    print("=" * 55)
    print(f"  LiveKit URL: {LIVEKIT_URL}")
    print()

    lkapi = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=API_KEY,
        api_secret=API_SECRET,
    )
    sip = lkapi.sip

    created_inbound_trunks = []
    created_dispatch_rules = []

    # ── 1. Create Inbound Trunk (واحد يشمل كل الأرقام) ─────────────────────
    all_numbers = [m["number"] for m in NUMBER_PERSONA_MAP if m["number"]]

    if not all_numbers:
        print("⚠️  لا توجد أرقام محددة في SIP_PROVIDER_NUMBERS — تخطي إنشاء Inbound Trunk")
    else:
        print(f"[1/3] إنشاء Inbound Trunk للأرقام: {all_numbers}")
        inbound_trunk = await sip.create_inbound_trunk(
            CreateSIPInboundTrunkRequest(
                trunk=SIPInboundTrunkInfo(
                    name="call-center-inbound",
                    numbers=all_numbers,
                    auth_username=SIP_USERNAME,
                    auth_password=SIP_PASSWORD,
                )
            )
        )
        created_inbound_trunks.append(inbound_trunk)
        print(f"  ✅ Inbound Trunk ID: {inbound_trunk.sip_trunk_id}")
        print()

        # ── 2. Create Dispatch Rule لكل رقم/persona ─────────────────────────
        print("[2/3] إنشاء Dispatch Rules ...")
        for mapping in NUMBER_PERSONA_MAP:
            if not mapping["number"]:
                continue
            persona   = mapping["persona"]
            prefix    = mapping["room_prefix"]
            name      = mapping["name"]
            metadata  = json.dumps({"persona": persona}, ensure_ascii=False)

            dispatch = await sip.create_dispatch_rule(
                CreateSIPDispatchRuleRequest(
                    dispatch_rule=SIPDispatchRuleInfo(
                        name=f"dispatch-{persona}",
                        trunk_ids=[inbound_trunk.sip_trunk_id],
                        rule=SIPDispatchRule(
                            dispatch_rule_individual=SIPDispatchRuleIndividual(
                                room_prefix=prefix,
                            )
                        ),
                        room_config=RoomConfiguration(
                            agents=[RoomAgent(
                            agent_name="inbound-agent",
                            metadata=metadata,
                        )]
                        ),
                    )
                )
            )
            created_dispatch_rules.append(dispatch)
            print(f"  ✅ [{name}] Dispatch Rule ID: {dispatch.sip_dispatch_rule_id} | prefix={prefix} | persona={persona}")

        print()

    # ── 3. Create Outbound Trunk (اختياري) ──────────────────────────────────
    if SIP_OUTBOUND_HOST and all_numbers:
        print("[3/3] إنشاء Outbound Trunk ...")
        outbound_trunk = await sip.create_outbound_trunk(
            CreateSIPOutboundTrunkRequest(
                trunk=SIPOutboundTrunkInfo(
                    name="call-center-outbound",
                    address=SIP_OUTBOUND_HOST,
                    numbers=all_numbers,
                    auth_username=SIP_USERNAME,
                    auth_password=SIP_PASSWORD,
                )
            )
        )
        print(f"  ✅ Outbound Trunk ID: {outbound_trunk.sip_trunk_id}")
        print()
        print("  💡 احفظ الـ Outbound Trunk ID في .env.local:")
        print(f"     SIP_OUTBOUND_TRUNK_ID={outbound_trunk.sip_trunk_id}")
    else:
        print("[3/3] تخطي Outbound Trunk (SIP_OUTBOUND_HOST غير محدد)")

    await lkapi.aclose()

    print()
    print("=" * 55)
    print("  ✅ Setup اكتمل!")
    print("=" * 55)
    print()
    print("الخطوات التالية:")
    print("  1. تأكد من تشغيل ngrok: ngrok http 7880")
    print("  2. أضف الـ ngrok URL كـ Origination URI في Twilio:")
    print("     sip:<ngrok-subdomain>.ngrok-free.app;transport=tcp")
    print("  3. شغّل المشروع: ./start-local.sh")
    print("  4. اتصل على رقمك وكلّم فهد! 🎉")


if __name__ == "__main__":
    asyncio.run(main())
