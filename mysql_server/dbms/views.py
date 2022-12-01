from django.shortcuts import render
from django.http.response import HttpResponse
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import viewsets, filters
from .serializers import *
from .models import *
from .common import CustomPagination
# from django_filters.rest_framework import DjangoFilterBackend
from django.http import Http404, HttpResponse
from rest_framework.exceptions import APIException
import pymysql
from .tasks import install_mysql_by_ansible
import time

class SchemaViewSet(viewsets.ModelViewSet):
    queryset = SchemaModel.objects.all()
    serializer_class = SchemaSerializer
    pagination_class = CustomPagination
    # filter_backends = [DjangoFilterBackend]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']



    @action(detail=False, methods=['get'])
    def get_distinct_schema_names(self, request, *args, **kwargs):
    # def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().values('name').distinct()
        # 我们这里没有使用序列化器，而是将query set变成了一个列表返回
        name_list = [d["name"] for d in list(queryset)]
        # print(name_list)
        return Response(name_list)


class InstanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InstanceModel.objects.all()
    serializer_class = InstanceSerializer
    pagination_class = CustomPagination

    def filter_queryset(self, queryset):
        schema = self.request.query_params.get('schema', None)
        if schema:
            queryset = queryset.filter(schema=schema)
        return queryset

    @action(detail=False, methods=['POST'])
    def install_mysql(self, request, *args, **kwargs):
        serializer = MySQLInstallSerializer(data=request.data)
        serializer.is_valid()
        if InstanceModel.objects.filter(host_ip=serializer.validated_data['host_ip'],
                                        port=serializer.validated_data['port']).exists():
            raise ValidationError('this ip has already exist')
        if SchemaModel.objects.filter(name=serializer.validated_data['schema']).exists():
            print('schema exist')
            schema = SchemaModel.objects.get(name=serializer.validated_data['schema'])
            instance = InstanceModel.objects.create(host_ip=serializer.validated_data['host_ip'],
                                                    port=serializer.validated_data['port'], schema=schema,
                                                    status=InstanceModel.PENDING, role="master")
            instance.save()
            install_mysql_by_ansible.delay(instance.id)
        elif not SchemaModel.objects.filter(name=serializer.validated_data['schema']).exists():
            print('schema is not exist')
            schema = SchemaModel.objects.create(name=serializer.validated_data['schema'],
                                                create_time=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            instance = InstanceModel.objects.create(host_ip=serializer.validated_data['host_ip'],
                                                    port=serializer.validated_data['port'], schema=schema,
                                                    status=InstanceModel.PENDING, role="master")
            schema.save()
            instance.save()
            install_mysql_by_ansible.delay(instance.id)
        return Response("success")

    @action(detail=True, methods=['GET'])
    def get_process_list(self, request, pk=None, *args, **kwargs):
        if pk is None:
            raise Http404
        try:
            db = self.get_connection(pk)
            c = db.cursor()
            c.execute("show processlist;")
            results = c.fetchall()  # 获取所有数据
            columns = ["id", "user", "host", "db", "command", "time", "state", "info"]

            process_list = []
            for row in results:
                d = {}
                for idx, col_name in enumerate(columns):
                    d[col_name] = row[idx]
                process_list.append(d)
            c.close()
            db.close()
            return Response(process_list)
        except Exception:
            raise APIException("无法获取process list")

    @action(detail=True, methods=['delete'])
    def kill_process_list(self, request, pk=None):
        if pk is None:
            raise Http404
        serializer = KillMySQLProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        process_id = serializer.validated_data.get('process_id')
        db = self.get_connection(pk)
        c = db.cursor()
        c.execute("kill %d;" % process_id)
        c.close()
        db.close()
        return Response("success")
    def get_connection(self, instance_id):
        instance = self.get_queryset().get(pk=instance_id)
        # TODO: dbUtils 连接池性能更好
        db = pymysql.connect(host=instance.host_ip, port=instance.port, user="root",
                              passwd="letsg0", charset='utf8', connect_timeout=2)
        #db = pymysql.connect(host='192.168.164.11', port=3306, user="root",
                             #passwd="Root.12345", database='django', charset='utf8', connect_timeout=2)
        return db


class AnsibleResultViews(viewsets.ReadOnlyModelViewSet):
    queryset = AnsibleTaskResult.objects.all()
    serializer_class = AnsibleTaskSerializer
    pagination_class = CustomPagination
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ('start_time',)

