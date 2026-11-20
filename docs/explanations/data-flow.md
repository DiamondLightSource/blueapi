# Where Data Goes: Numtracker, Detectors, Tiled and NeXus

This page follows one run of the `count` plan on the `det` detector through
blueapi. It covers where the file path comes from, which component writes the
detector file, and how the documents reach Tiled and the NeXus file writer.

The outputs below come from a real run against the local stack
(see [Run BlueAPI and connect to services locally](../how-to/just-run-blueapi-and-services-locally.md)).

## The big picture

```{raw} html
:file: ../images/blueapi-data-flow.excalidraw.svg
```

Three points to take from the diagram:

1. **Numtracker decides the path, the detector writes the file.** Numtracker
   hands out a scan number and a directory. The path provider turns them into
   a file name. The detector (here the areaDetector IOC's HDF5 plugin) writes
   the frames. Neither blueapi, Tiled nor the NeXus writer writes detector data.
2. **The RunEngine sends every document down two channels.** One goes over
   STOMP to RabbitMQ. The other goes straight to Tiled over HTTP.
3. **Tiled and NeXus learn where the data is from the `stream_resource`
   document.** Each one records a reference to the detector's file. Neither
   copies the frames.

## Step 1: The RunEngine asks numtracker for a scan

`blueapi.service.interface.context()` sets the RunEngine's `scan_id_source`.
On every `open_run` the RunEngine calls it with the run metadata, and it calls
numtracker:

```python
async def _update_scan_num(md: dict[str, Any]) -> int:
    scan = await nt.create_scan(md["instrument_session"], md["instrument"])
    md["data_session_directory"] = str(scan.scan.directory.path)
    md["detector_file_template"] = nt_conf.detector_file_template
    md["scan_file"] = scan.scan.scan_file
    return scan.scan.scan_number
```

The two names refer to the same idea from different sides:

| Term | Used by | Meaning | Example |
| --- | --- | --- | --- |
| `instrument_session` | DLS / numtracker | The visit: proposal and visit number | `cm12345-1` |
| `data_session_directory` | bluesky / ophyd-async | Where detectors should write | `/tmp` locally, `/dls/<instrument>/data/<year>/<visit>` in production |

### Where the directory comes from

Blueapi does not choose the directory. Numtracker builds it from the
`directory` template configured for each instrument. The local stack configures
`adsim` with `directory: "/tmp/"` (see `tests/system_tests/services/startup.py`)
because the containers have no `/dls` mount. In production the instrument is
configured with a template like `/dls/{instrument}/data/{year}/{visit}`, so the
same code path produces, for example,
`/dls/i22/data/2026/cm12345-1/i22-44-det.h5`.

To change it, reconfigure numtracker for the instrument. Blueapi's config and
helm chart don't need changing. The path must exist on the machines that use
it:

| Component | Needs the `/dls` path? | Why |
| --- | --- | --- |
| Detector IOC | Yes, writable | It writes the HDF5 file |
| NeXus file writer | Yes, writable | It writes the `.nxs` file that links to the detector file |
| Tiled server | Yes, readable | It opens the file when someone reads the data |
| Blueapi pod | No, by default | It only passes the path along in documents. Mount it with the chart's `volumes`/`volumeMounts` only if a plan reads data files itself |

## Step 2: The path provider turns metadata into a file path

When numtracker is configured, `BlueskyContext` creates a
`StartDocumentPathProvider` and subscribes it to `start` and `stop` documents.
It keeps the newest start document. When a detector asks for a path, it fills
`detector_file_template` from that document.

A temporary `print` added to `StartDocumentPathProvider.run_start` and
`__call__` showed this during the test run:

```text
PATH PROVIDER run_start: {'instrument': 'adsim', 'instrument_session': 'cm12345-1',
    'scan_id': 44, 'scan_file': 'adsim-44', 'data_session_directory': '/tmp',
    'detector_file_template': '{instrument}-{scan_id}-{device_name}'}
PATH PROVIDER __call__('det') -> directory_path=PosixPath('/tmp') filename='adsim-44-det'
    create_dir_depth=0 directory_uri='file://localhost/tmp/'
```

So numtracker returned scan `44` and directory `/tmp`, and the detector `det`
was told to write `/tmp/adsim-44-det` (the HDF writer adds `.h5`).

## Step 3: The detector writes the file

`det` is an ophyd-async `StandardDetector`. During `prepare`, it gives the path
to the IOC's HDF5 file plugin, and the IOC writes the frames. The file lives on
the **IOC's** filesystem. Locally, `/tmp/adsim-44-det.h5` exists inside the
`bl01t-di-cam-01` container and not on the host running blueapi:

```text
$ ls /tmp/adsim-44-det.h5
"/tmp/adsim-44-det.h5": No such file or directory
$ docker exec system_tests-bl01t-di-cam-01-1 ls -la /tmp/adsim-44-det.h5
-rw-r--r-- 1 root root 3158576 Nov 19 00:07 /tmp/adsim-44-det.h5
```

Inside the file the frames are at `/entry/data/data`. Nothing in the file is
called `det`:

```text
entry/data/data (2, 1024, 1024)
entry/instrument/NDAttributes/NDArrayUniqueId (2,)
...
```

The detector then tells the RunEngine what it wrote by emitting documents.

## Step 4: The documents

These are all the documents for `count(detectors=["det"], num=2)`, as received
from the message bus (shortened):

```text
start            scan_id=44, scan_file=adsim-44, data_session_directory=/tmp,
                 instrument_session=cm12345-1, plan_name=count
descriptor       name=primary
                 data_keys.det = {source: file://localhost/tmp/adsim-44-det.h5,
                                  shape: [1, 1024, 1024], external: "STREAM:"}
stream_resource  uid=1effd20a..., data_key=det, mimetype=application/x-hdf5,
                 uri=file://localhost/tmp/adsim-44-det.h5,
                 parameters={dataset: /entry/data/data, chunk_shape: [1, 1024, 1024]}
stream_datum     stream_resource=1effd20a..., indices 0→1, seq_nums 1→2
event            seq_num=1, data={}          ← no pixels: they are in the file
stream_datum     stream_resource=1effd20a..., indices 1→2, seq_nums 2→3
event            seq_num=2, data={}
stop             exit_status=success, num_events={primary: 2}
```

- `external: "STREAM:"` in the descriptor means the data for `det` is not inside
  the events. Find it through `stream_resource` and `stream_datum` instead.
- `stream_resource` links the data key `det` to a file (`uri`) and a location
  inside the file (`parameters.dataset`).
- Each `stream_datum` says which frames (`indices`) belong to which events
  (`seq_nums`).

## Step 5: Two channels out of the RunEngine

### Message bus (RabbitMQ) and the NeXus file writer

`TaskWorker` subscribes `_on_document` to the RunEngine. Each document is
wrapped in a `DataEvent` and published over STOMP to the topic
`public.worker.event`. Worker state and progress events go to the same topic.

The NeXus file writer (`nexus-file-converter`, `just compose-diamond`) consumes
that topic. It builds the `.nxs` file from the documents, and links to the
detector file named in `stream_resource`. It never receives the frames.

### Tiled

For each task, `begin_task` subscribes a bluesky `TiledWriter` to the RunEngine.
It writes into the container `<instrument>/<proposal>/<instrument_session>/`, so
this run ended up at `adsim/cm12345/cm12345-1/<start uid>/primary`.

`TiledWriter` turns `stream_resource` and `stream_datum` into a Tiled **data
source** with an external asset. Tiled stores a pointer, not a copy:

```json
"data_sources": [{
  "structure_family": "array",
  "mimetype": "application/x-hdf5",
  "management": "external",
  "parameters": {"dataset": "/entry/data/data", "swmr": true},
  "assets": [{"data_uri": "file://localhost/tmp/adsim-44-det.h5"}],
  "structure": {"shape": [2, 1024, 1024]}
}]
```

When someone reads `primary/det`, Tiled opens that file and reads
`/entry/data/data`. This only works if the Tiled server can reach the same
filesystem path, which is why production detectors write to shared visit
directories.

## FAQ: How does Tiled find `AndorMarana` when the HDF5 file has no such dataset?

Data keys and HDF5 dataset names are separate things.

- **The data key** (`AndorMarana`, `det`) is the bluesky name for the
  measurement. It usually comes from the device name. It is the key in the
  descriptor's `data_keys` and the node name under `primary/` in Tiled.
- **The `source`** field of a data key only gives the file. It does not say
  where in the file the data is.
- **The location inside the file** comes from the `stream_resource` document,
  in `parameters.dataset`. For ophyd-async areaDetector HDF writers, the frames
  usually live at `/entry/data/data`, whatever the detector is called.

`TiledWriter` copies `uri` and `parameters` from `stream_resource` into the data
source of the `primary/AndorMarana` array node. Tiled reads from there and never
looks for a dataset called `AndorMarana`. Our run shows the same: the data key is
`det` but the frames are at `/entry/data/data`.

To check this on the real I08-1 run, open the array node rather than `primary/`
and look at its data sources:

```text
https://tiled.diamond.ac.uk/api/v1/metadata/i08-1/cm44149/cm44149-5/b8ebaf6b-d66f-4a7e-9677-7d5fcfec871a/primary/AndorMarana?include_data_sources=true
```

`data_sources[0].parameters.dataset` names the HDF5 path, and
`data_sources[0].assets[].data_uri` names the file(s).

## Reproduce it yourself

1. Start the stack with `just compose` and `just serve`. Add the temporary print
   to `src/blueapi/utils/path_provider.py` if you want to see the path provider
   output.
2. Watch the message bus. Use either of these:
   - `just listen` (`blueapi controller -o full listen`). It waits for Enter,
     so run it in an interactive terminal.
   - The raw script, which prints every message as JSON:

     ```{literalinclude} ../resources/print_message_bus.py
     :language: python
     ```

     `uv run python docs/resources/print_message_bus.py`
3. Run the plan: `just run count '{"detectors": ["det"], "num": 2}'`
4. Look for the run in Tiled under `adsim/cm12345/cm12345-1/` at
   <http://localhost:4181>.
