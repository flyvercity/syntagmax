from gitreqms.extractors.filename import FilenameArtifact, FilenameExtractor


class ObsidianArtifact(FilenameArtifact):
    def driver(self) -> str:
        return 'obsidian'


class ObsidianExtractor(FilenameExtractor):
    def loglabel(self) -> str:
        return 'OBSIDIAN'
