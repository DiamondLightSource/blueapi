# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import warnings

import grpc
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2
from services.proto import worker_pb2 as services_dot_proto_dot_worker__pb2

GRPC_GENERATED_VERSION = '1.65.1'
GRPC_VERSION = grpc.__version__
EXPECTED_ERROR_RELEASE = '1.66.0'
SCHEDULED_RELEASE_DATE = 'August 6, 2024'
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    warnings.warn(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + ' but the generated code in services/proto/worker_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
        + f' This warning will become an error in {EXPECTED_ERROR_RELEASE},'
        + f' scheduled for release on {SCHEDULED_RELEASE_DATE}.',
        RuntimeWarning
    )


class WorkerServiceStub:
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.GetWorkerState = channel.unary_unary(
                '/WorkerService/GetWorkerState',
                request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
                response_deserializer=services_dot_proto_dot_worker__pb2.WorkerStateMessage.FromString,
                _registered_method=True)
        self.SetWorkerState = channel.unary_unary(
                '/WorkerService/SetWorkerState',
                request_serializer=services_dot_proto_dot_worker__pb2.StateChangeRequest.SerializeToString,
                response_deserializer=services_dot_proto_dot_worker__pb2.WorkerStateMessage.FromString,
                _registered_method=True)
        self.SubmitTask = channel.unary_unary(
                '/WorkerService/SubmitTask',
                request_serializer=services_dot_proto_dot_worker__pb2.Task.SerializeToString,
                response_deserializer=services_dot_proto_dot_worker__pb2.TaskResponse.FromString,
                _registered_method=True)
        self.GetTasks = channel.unary_unary(
                '/WorkerService/GetTasks',
                request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
                response_deserializer=services_dot_proto_dot_worker__pb2.TasksListResponse.FromString,
                _registered_method=True)
        self.GetActiveTask = channel.unary_unary(
                '/WorkerService/GetActiveTask',
                request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
                response_deserializer=services_dot_proto_dot_worker__pb2.WorkerTask.FromString,
                _registered_method=True)
        self.SetActiveTask = channel.unary_unary(
                '/WorkerService/SetActiveTask',
                request_serializer=services_dot_proto_dot_worker__pb2.WorkerTask.SerializeToString,
                response_deserializer=services_dot_proto_dot_worker__pb2.WorkerTask.FromString,
                _registered_method=True)
        self.GetWorkerEvent = channel.unary_unary(
                '/WorkerService/GetWorkerEvent',
                request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
                response_deserializer=services_dot_proto_dot_worker__pb2.WorkerEvent.FromString,
                _registered_method=True)


class WorkerServiceServicer:
    """Missing associated documentation comment in .proto file."""

    def GetWorkerState(self, request, context):
        """Get the state of the worker.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetWorkerState(self, request, context):
        """Change the state of the worker.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SubmitTask(self, request, context):
        """Submit a task to the worker.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetTasks(self, request, context):
        """Get a list of tasks.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetActiveTask(self, request, context):
        """Get the active task of the worker.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetActiveTask(self, request, context):
        """Set a task as active.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetWorkerEvent(self, request, context):
        """Get events from the worker.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_WorkerServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'GetWorkerState': grpc.unary_unary_rpc_method_handler(
                    servicer.GetWorkerState,
                    request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                    response_serializer=services_dot_proto_dot_worker__pb2.WorkerStateMessage.SerializeToString,
            ),
            'SetWorkerState': grpc.unary_unary_rpc_method_handler(
                    servicer.SetWorkerState,
                    request_deserializer=services_dot_proto_dot_worker__pb2.StateChangeRequest.FromString,
                    response_serializer=services_dot_proto_dot_worker__pb2.WorkerStateMessage.SerializeToString,
            ),
            'SubmitTask': grpc.unary_unary_rpc_method_handler(
                    servicer.SubmitTask,
                    request_deserializer=services_dot_proto_dot_worker__pb2.Task.FromString,
                    response_serializer=services_dot_proto_dot_worker__pb2.TaskResponse.SerializeToString,
            ),
            'GetTasks': grpc.unary_unary_rpc_method_handler(
                    servicer.GetTasks,
                    request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                    response_serializer=services_dot_proto_dot_worker__pb2.TasksListResponse.SerializeToString,
            ),
            'GetActiveTask': grpc.unary_unary_rpc_method_handler(
                    servicer.GetActiveTask,
                    request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                    response_serializer=services_dot_proto_dot_worker__pb2.WorkerTask.SerializeToString,
            ),
            'SetActiveTask': grpc.unary_unary_rpc_method_handler(
                    servicer.SetActiveTask,
                    request_deserializer=services_dot_proto_dot_worker__pb2.WorkerTask.FromString,
                    response_serializer=services_dot_proto_dot_worker__pb2.WorkerTask.SerializeToString,
            ),
            'GetWorkerEvent': grpc.unary_unary_rpc_method_handler(
                    servicer.GetWorkerEvent,
                    request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                    response_serializer=services_dot_proto_dot_worker__pb2.WorkerEvent.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'WorkerService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('WorkerService', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class WorkerService:
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def GetWorkerState(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/WorkerService/GetWorkerState',
            google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            services_dot_proto_dot_worker__pb2.WorkerStateMessage.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def SetWorkerState(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/WorkerService/SetWorkerState',
            services_dot_proto_dot_worker__pb2.StateChangeRequest.SerializeToString,
            services_dot_proto_dot_worker__pb2.WorkerStateMessage.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def SubmitTask(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/WorkerService/SubmitTask',
            services_dot_proto_dot_worker__pb2.Task.SerializeToString,
            services_dot_proto_dot_worker__pb2.TaskResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def GetTasks(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/WorkerService/GetTasks',
            google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            services_dot_proto_dot_worker__pb2.TasksListResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def GetActiveTask(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/WorkerService/GetActiveTask',
            google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            services_dot_proto_dot_worker__pb2.WorkerTask.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def SetActiveTask(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/WorkerService/SetActiveTask',
            services_dot_proto_dot_worker__pb2.WorkerTask.SerializeToString,
            services_dot_proto_dot_worker__pb2.WorkerTask.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def GetWorkerEvent(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/WorkerService/GetWorkerEvent',
            google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            services_dot_proto_dot_worker__pb2.WorkerEvent.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
