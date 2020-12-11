# easylogger
A relatively simple logging configuration for Python scripts with just enough customization for my projects' needs.

## Install
Remote (my currently preferred way)
```bash
python3 -m pip install git+https://github.com/barretobrock/easylogger.git#egg=easylogger
```
Local
```bash
python3 -m pip install .
```

## Examples
Logging
```python
from easylogger import Log


# Create a log object that binds to the console for output and also sends output to a file in ~{USER}/logs. Exceptions are automatically caught and also written to the log file. 
log = Log('my_log', log_level_str='DEBUG', log_to_file=True)
log.debug('Debug message.')

# Make a child log embedded in a class, which gets appended to the parent log
class SomethingFancy:
    def __init__(self, parent_log: Log):
        self.log = Log(parent_log, child_name=self.__class__.__name__)

    def do_something(self, thing: str):
        self.log.info(f'Detected this: {thing}...')
        # Try something weird
        try:
            wrong = float(thing)
        except Exception as e:
            # Maybe we just want to log this?
            self.log.error_from_class(e, 'Uncaught exception!')
```
Argument parsing
```python
from easylogger import ArgParse


# Create the list of arguments
arg_list = [
    {
        'names': ['-t', '--this'],
        'other': {
            'action': 'store',
            'default': 'hello'
        }
    }
]
ap = ArgParse(arg_list, parse_all=False)
args = ap.parse()
# Print to see the result of the argument passed in, with default of 'hello' used.
print(args[0].this)
```

## Testing
Tests can be run with a simple command:
```bash
tox
```