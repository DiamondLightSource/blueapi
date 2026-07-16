# Run a Plan from Docs page

:::{note}
This page describes how to run a plan from the docs page for the p-xx testing rigs. 
:::

Following [this link](https://p46-blueapi.diamond.ac.uk/docs), will take you to the blueapi docs for p46. After keycloak login, you should see the page below. 

![BlueAPI docs page](blueapi-docs-page.png)

Scrolling down will show you endpoints grouped. The different groups are described below. 

Definitions:
- Plan: a set of instructions for one aspect of experiment orchestration. More details can be found [here](https://blueskyproject.io/bluesky/v1.13.1rc1/plans.html)
- Task: one individual instance of the plan being run. 
- Device: devices defined in ophyd-async(?). [This](https://blueskyproject.io/bluesky/v1.13.1rc1/tutorial.html#devices) is Bluesky's definition of a device. Maybe mention dodal here and add link?
- Environment - definition already provided
- Meta - definition already provided 

Steps for running a plan
1. Find available devices. 

The first recommended step is to find out what devices are available for use to run a plan. Scroll down to the Get Devices endpoint (/api/v1/devices) and Press the downwards arrow which should expand it to show to 'Try it out' button. 

![Find devices endpoint](find_devices.png)

Next, press the 'Execute' button and scroll down to Responses where you should see available devices (e.g. 'det' in the example below). Select one of these devices. 

![Show devices](show_devices.png)

2. Submit a task using one of the available devices.

Scroll back up to the Submit Task endpoint (/api/v1/tasks). The default setting that should appear in the request body is the example of a 'count' task using detector 'x' and instrument session 'cm12345-1'. 

![Submit task default](submit_task.png)

Press the 'Try it out' button and replace the placeholder 'x' in the request body with the device selected from step 1 ('det' in this example) and 'cm12345-1' with the correct instrument session details ('cm44194-1') which can be found on the #sscc-training-room slack channel. 

![Submit task with details](put_task_with_details.png)

Troubleshooting
