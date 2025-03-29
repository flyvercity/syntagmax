from gitreqms.extractors.filename import FilenameArtifact, FilenameExtractor


class ObsidianArtifact(FilenameArtifact):
    def driver(self) -> str:
        return 'obsidian'


class ObsidianExtractor(FilenameExtractor):
    def extractor(self) -> str:
        return 'OBSIDIAN'
