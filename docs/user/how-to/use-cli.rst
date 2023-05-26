Use the command line interface (CLI)
====================================

Blueapi comes pacakged with a simple click based CLI. You can start the server
and then query it for plans and devices, as well as ask it to run a plan, through
the CLI.

Starting the server
-------------------
You can start the server and optionally specify configuration options (see the
documentation section on how to :doc:`configure blueapi <./configure-app>`) with
the following command::
    blueapi serve

The default configuration options for this command will start up the server using 
startup scripts found in `src/blueapi/startup` - this will initialise the server
with existing plans and devices that can be run with those plans.

Find devices
------------
A list of all usable devices can be retrieved with the following command::
    blueapi controller devices

Find plans
----------
A list of all plans runnable by the server can be queried with::
    blueapi controller plans

Run a plan
----------
To run a plan, you must specify a valid name of a plan with correct parameters.
The 'sleep' command would need to be run like so::
    blueapi controller run sleep '{"time": 2.0}'

where `2.0` can be any number. By default, the worker will try to run the plan
until completion, but you can specify a timeout::
    blueapi controller run sleep '{"time": 2.0}' -t 1.0

In this case, this will fail with a timeout error.
