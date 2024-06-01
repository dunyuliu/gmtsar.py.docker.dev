import logging
import pathlib
import os
from dependency import foo, bar, baz


logging.basicConfig(level=logging.DEBUG, filename='test.log', filemode='w')
main_logger = logging.getLogger(__name__)
main_logger.setLevel(logging.DEBUG)
main_logger.info('This is the main logger')
main_logger.debug('This is the main logger debug')
main_logger.critical('This is the main logger critical')

foo()

bar()

baz()


current = pathlib.Path(os.getcwd())
print(current)
print(current.parent)

pathtest = pathlib.Path('Pythonictesting')
full = pathtest.resolve()
print(full)
print(pathtest.parent.parent)
