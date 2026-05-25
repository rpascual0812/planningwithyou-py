from django.http import Http404, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from planningwithyou.file_storage import (
    read_booking_pdf_file,
    read_company_logo_file,
    read_document_file,
    read_user_photo_file,
)
from users.scope import users_for_user
from planningwithyou.permissions import HasAccount, HasCompany


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

    permission_classes = [IsAuthenticated, HasAccount, HasCompany]

    def get(self, request, document_id: int):
        try:
            data, filename, content_type = read_document_file(
                document_id,
                account_id=request.user.account_id,
                company_id=request.user.company_id,
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

    permission_classes = [IsAuthenticated, HasAccount, HasCompany]

    def get(self, request, booking_id: int):
        try:
            data, filename, content_type = read_booking_pdf_file(
                booking_id,
                account_id=request.user.account_id,
                company_id=request.user.company_id,
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


class CompanyLogoFileView(APIView):
    """Serve a company logo by company id (hides underlying S3/storage path)."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request, company_id: int):
        try:
            data, filename, content_type = read_company_logo_file(
                company_id,
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


class UserPhotoFileView(APIView):
    """Serve a user profile photo by user id."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request, user_id: int):
        if not users_for_user(request.user).filter(pk=user_id).exists():
            raise Http404('User not found.')
        try:
            data, filename, content_type = read_user_photo_file(
                user_id,
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
