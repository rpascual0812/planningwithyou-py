from django.http import Http404, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from planningwithyou.file_storage import (
    read_account_logo_file,
    read_booking_pdf_file,
    read_document_file,
)
from planningwithyou.permissions import HasAccount


def _as_attachment(request) -> bool:
    return request.query_params.get('download', '').lower() in {
        '1',
        'true',
        'yes',
    }


def _file_response(
    data: bytes,
    filename: str,
    content_type: str,
    *,
    as_attachment: bool,
) -> HttpResponse:
    disposition = 'attachment' if as_attachment else 'inline'
    safe_name = filename.replace('"', '')
    response = HttpResponse(data, content_type=content_type)
    response['Content-Disposition'] = f'{disposition}; filename="{safe_name}"'
    response['Content-Length'] = len(data)
    return response


class DocumentFileView(APIView):
    """Download a document by id (hides underlying S3/storage path)."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request, document_id: int):
        try:
            data, filename, content_type = read_document_file(
                document_id,
                account_id=request.user.account_id,
            )
        except FileNotFoundError as exc:
            raise Http404(str(exc)) from exc
        except ValueError as exc:
            return HttpResponse(str(exc), status=413)

        return _file_response(
            data,
            filename,
            content_type,
            as_attachment=_as_attachment(request),
        )


class BookingPdfFileView(APIView):
    """Download a booking quote PDF by booking id."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request, booking_id: int):
        try:
            data, filename, content_type = read_booking_pdf_file(
                booking_id,
                account_id=request.user.account_id,
            )
        except FileNotFoundError as exc:
            raise Http404(str(exc)) from exc
        except ValueError as exc:
            return HttpResponse(str(exc), status=413)

        return _file_response(
            data,
            filename,
            content_type,
            as_attachment=_as_attachment(request),
        )


class AccountLogoFileView(APIView):
    """Serve an account logo by account id (hides underlying S3/storage path)."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request, account_id: int):
        try:
            data, filename, content_type = read_account_logo_file(account_id)
        except FileNotFoundError as exc:
            raise Http404(str(exc)) from exc
        except ValueError as exc:
            return HttpResponse(str(exc), status=413)

        return _file_response(
            data,
            filename,
            content_type,
            as_attachment=_as_attachment(request),
        )
