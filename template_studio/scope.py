from __future__ import annotations

from template_studio.models import InvitationTemplate


def templates_for_user(user):
    return InvitationTemplate.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
        is_marketplace=False,
    )
