from django.shortcuts import get_object_or_404, render
from django.db import transaction

from rest_framework.viewsets import ModelViewSet
from rest_framework.serializers import ModelSerializer, IntegerField
from rest_framework.exceptions import ValidationError
from course_api.tasks.models import Board, Status, Task
from rest_framework.permissions import IsAuthenticated


class BoardSerializer(ModelSerializer):
    class Meta:
        model = Board
        exclude = ("created_by", "external_id", "deleted")


class StatusSerializer(ModelSerializer):
    class Meta:
        model = Status
        exclude = ("created_by", "external_id", "deleted")


class TaskSerializer(ModelSerializer):
    board_object = BoardSerializer(source="board", read_only=True)
    status_object = StatusSerializer(source="status", read_only=True)
    status = IntegerField(required=True, write_only=True)

    class Meta:
        model = Task
        exclude = ("external_id", "deleted")

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        user = self.context["request"].user
        status = validated_data["status"]
        # future option : check for created_by user if not multi user board
        status_obj = Status.objects.filter(id=status).first()
        if not status_obj:
            raise ValidationError({"status": "not found"})
        validated_data["status"] = status_obj
        return validated_data


class BoardViewset(ModelViewSet):
    queryset = Board.objects.all()
    serializer_class = BoardSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(created_by=self.request.user)


class StatusViewset(ModelViewSet):
    queryset = Status.objects.all()
    serializer_class = StatusSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(created_by=self.request.user)


class NestedStatusViewSet(ModelViewSet):
    queryset = Status.objects.all()
    serializer_class = StatusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        board = get_object_or_404(
            Board.objects.filter(
                id=self.kwargs["boards_pk"], created_by=self.request.user
            )
        )
        return self.queryset.filter(board=board)

    def perform_create(self, serializer):
        board = get_object_or_404(
            Board.objects.filter(
                id=self.kwargs["boards_pk"], created_by=self.request.user
            )
        )
        serializer.save(board=board,created_by=self.request.user)


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        board = get_object_or_404(
            Board.objects.filter(
                id=self.kwargs["boards_pk"], created_by=self.request.user
            )
        )
        return self.queryset.filter(board=board).order_by("completed","priority")

    def perform_create(self, serializer):
        board = get_object_or_404(
            Board.objects.filter(
                id=self.kwargs["boards_pk"], created_by=self.request.user
            )
        )
        cascade_priority(
            board,
            serializer.validated_data["status"],
            serializer.validated_data["priority"],
        )
        serializer.save(board=board)

    def perform_update(self, serializer):
        cascade_priority(
            serializer.validated_data["board"],
            serializer.validated_data["status"],
            serializer.validated_data["priority"],
        )
        serializer.save()


def cascade_priority(board, status, priority):
    if Task.objects.filter(board=board, status=status, priority=priority).exists():
        updateSet = []
        p = priority
        parseDB = (
            Task.objects.select_for_update()
            .filter(board=board, status=status, priority__gte=priority)
            .order_by("priority")
        )
        with transaction.atomic():
            for task in parseDB:
                if task.priority == p:
                    task.priority += 1
                    p += 1
                    updateSet.append(task)
        n = Task.objects.bulk_update(updateSet, ["priority"])
