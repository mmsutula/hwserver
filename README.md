# hwserver

This is a light wrapper to https://github.com/mwalsh161/ModuleServer including various shared hardware objects interfaced by python.

## Installation

 + Install `python3` via `anaconda`.
 + Clone a local copy of hwserver (this repository).
 + Initialize the ModuleServer submodule with `git submodule update --init`.
  + In the future, when pulling ModuleServer updates, use `git submodule update`.
 + Copy the appropriate modules from example.config to the new file server.config to configure this local instance of hwserver.
  + Note that modules named with an underscore `_` in front are ignored by the config file, so such modules are effectively commented out.
 + Be sure that necessary packages (`serial`, `queue`) are installed on the appropriate conda environment.
  + These can be installed via `conda install serial queue`.
 + Open up a shell with `python3` and `conda`. Depending upon how anaconda was installed, it might be easiest to open a shell via Anaconda Navigator.
 + Start hwserver from the hwserver directory via `python server.py`.
  + You may need to use `python3` depending upon how your shell is configured.
  + Debugmode can be activated by adding any additional argument such as `python server.py 1`.
 + TODO: instructions for autostart with Windows!

## Debugging

+ Modules loaded on a hwserver instance are configured by the server.config file, which is not tracked by git. A base configuration is included in example.config. Underscored names are considered "comments" and ignored. This is a useful method to unload a module.
+ The server will listen on port 0.0.0.0:36577. *MAKE SURE YOUR FILEWALL ALLOWS THIS.*
+ The core of this repository consists of the instruments associated with it, noteably the msquared infrastructure is particular to how we have it set up, and may differ.
+ Be sure that old servers (such as the old PulseBlaster server) are not running; these can conflict with the new hwserver implementation.
