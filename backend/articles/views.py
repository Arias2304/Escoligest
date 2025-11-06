from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from coreusers.permissions import IsAdminUserRole
from .models import Article
from .serializers import (
    ArticleDetailSerializer,
    ArticlePublicSerializer,
    ArticleSubmitSerializer,
)


class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.select_related("created_by", "approved_by")
    serializer_class = ArticleDetailSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        if self.action in (
            "update",
            "partial_update",
            "destroy",
            "approve",
            "reject",
            "pending",
        ):
            return [permissions.IsAuthenticated(), IsAdminUserRole()]
        if self.action == "mine":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "list":
            return ArticlePublicSerializer
        if self.action == "create":
            return ArticleSubmitSerializer
        return ArticleDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            return queryset.filter(status=Article.STATUS_APPROVED)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        role = getattr(user, "role", "")
        if role not in ("ADMIN", "MEDIC"):
            raise PermissionDenied(
                "Solo medicos o administradores pueden registrar articulos."
            )
        article = serializer.save(created_by=user)
        if role == "ADMIN":
            article.mark_approved(user)
        else:
            if (
                article.status != Article.STATUS_PENDING
                or article.approved_by_id is not None
                or article.published_at is not None
            ):
                article.status = Article.STATUS_PENDING
                article.approved_by = None
                article.published_at = None
                article.review_notes = ""
                article.save(
                    update_fields=[
                        "status",
                        "approved_by",
                        "published_at",
                        "review_notes",
                        "updated_at",
                    ]
                )
        return article

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = self.perform_create(serializer)
        detail_serializer = ArticleDetailSerializer(
            article, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(detail_serializer.data)
        return Response(
            detail_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        if instance.status != Article.STATUS_APPROVED:
            if not request.user.is_authenticated:
                raise NotFound()
            if getattr(user, "role", "") != "ADMIN" and instance.created_by != user:
                raise NotFound()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def perform_destroy(self, instance):
        if instance.pdf:
            instance.pdf.delete(save=False)
        instance.delete()

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated, IsAdminUserRole],
    )
    def pending(self, request):
        queryset = self.get_queryset().filter(status=Article.STATUS_PENDING)
        serializer = ArticleDetailSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def mine(self, request):
        user = request.user
        if getattr(user, "role", "") not in ("ADMIN", "MEDIC"):
            raise PermissionDenied(
                "Solo medicos o administradores pueden consultar sus articulos."
            )
        queryset = self.get_queryset().filter(created_by=user)
        serializer = ArticleDetailSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsAdminUserRole],
    )
    def approve(self, request, pk=None):
        article = self.get_object()
        notes = request.data.get("review_notes", "")
        article.mark_approved(request.user, notes)
        serializer = ArticleDetailSerializer(
            article, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsAdminUserRole],
    )
    def reject(self, request, pk=None):
        article = self.get_object()
        notes = request.data.get("review_notes", "")
        article.mark_rejected(request.user, notes)
        serializer = ArticleDetailSerializer(
            article, context=self.get_serializer_context()
        )
        return Response(serializer.data)
