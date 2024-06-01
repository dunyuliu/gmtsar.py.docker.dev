"""
some meaninless code to import and test
"""
import logging

logger = logging.getLogger(__name__)

def foo():
    logger.info('This is the foo function')
    return 1

def bar():
    logger.error('This is the bar function')
    return 2

def baz():
    logger.warning('This is the baz function')
    return 3
