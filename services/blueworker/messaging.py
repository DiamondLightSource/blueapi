
from messages_pb2 import StatusView, ProgressEvent, TaskStatus, WorkerEvent, TrackableTask
import protobuf3

# Example of creating and serializing a protobuf message
status_view = StatusView(
    display_name="Example Status",
    current=0.5,
    initial=0.0,
    target=1.0,
    unit="units",
    precision=3,
    done=False,
    percentage=50.0,
    time_elapsed=10.0,
    time_remaining=5.0
)

serialized_status_view = status_view.SerializeToString()

# Example of deserializing a protobuf message
deserialized_status_view = StatusView()
deserialized_status_view.ParseFromString(serialized_status_view)
print(deserialized_status_view)

# Repeat the serialization and deserialization process for other messages


