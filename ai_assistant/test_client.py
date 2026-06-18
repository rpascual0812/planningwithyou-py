from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from ai_assistant.client import AiAssistantError, complete_json, _provider_error_message


class ProviderErrorMessageTests(SimpleTestCase):
    def test_authentication_error(self):
        from openai import AuthenticationError

        exc = AuthenticationError(
            'Invalid API key',
            response=MagicMock(status_code=401),
            body={'error': {'message': 'Incorrect API key provided'}},
        )
        message = _provider_error_message(exc)
        self.assertIn('API key', message)

    def test_not_found_error_includes_model(self):
        from openai import NotFoundError

        exc = NotFoundError(
            'Model not found',
            response=MagicMock(status_code=404),
            body={'error': {'message': 'The model does not exist'}},
        )
        with override_settings(AI_ASSISTANT_MODEL='gpt-4o-mini'):
            message = _provider_error_message(exc)
        self.assertIn('gpt-4o-mini', message)


class CompleteJsonErrorTests(SimpleTestCase):
    @override_settings(OPENAI_API_KEY='test-key')
    @patch('ai_assistant.client._client')
    def test_maps_openai_failure_to_actionable_message(self, mock_client_factory):
        from openai import AuthenticationError

        client = MagicMock()
        client.chat.completions.create.side_effect = AuthenticationError(
            'Invalid API key',
            response=MagicMock(status_code=401),
            body={'error': {'message': 'Incorrect API key provided'}},
        )
        mock_client_factory.return_value = client

        with self.assertRaises(AiAssistantError) as ctx:
            complete_json(system='sys', user='usr')

        self.assertIn('API key', str(ctx.exception))
