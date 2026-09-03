from rest_framework.pagination import CursorPagination


class DefaultCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    ordering = "-created_at"
