from rest_framework import permissions

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .access import ai_assistant_available_for_user, ai_assistant_configured


class HasAiAssistantAccess(permissions.BasePermission):
    """Require AI plan, configured provider, and ``ai_assistant`` feature write."""

    message = 'AI assistant is not available on your plan or is not configured.'

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if not ai_assistant_available_for_user(user):
            self.message = (
                'AI assistant requires an AI Plus subscription.'
            )
            return False
        feature = FeatureAccess()
        view.feature_key = 'ai_assistant'
        if not feature.has_permission(request, view):
            self.message = FeatureAccess.message
            return False
        return True


AI_ASSISTANT_PERMISSIONS = [
    permissions.IsAuthenticated,
    HasAccount,
    HasCompany,
    HasAiAssistantAccess,
]
