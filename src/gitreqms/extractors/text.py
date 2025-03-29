import logging as lg


class TextExtractor:
    def __init__(self, repo):
        self._repo = repo

    def process_file(self, file_name):
        lg.info(f'Processing file: {file_name}')
        pass
