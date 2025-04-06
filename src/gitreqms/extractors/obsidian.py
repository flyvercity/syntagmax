from gitreqms.extractors.filename import FilenameArtifact, FilenameExtractor

class ObsidianArtifact(FilenameArtifact):
    def driver(self) -> str:
        return 'obsidian'

class ObsidianExtractor(FilenameExtractor):
    def loglabel(self) -> str:
        return 'OBSIDIAN'

    def create_artifact(self, atype: str, aid: str, description: str) -> FilenameArtifact:
        return ObsidianArtifact(atype, aid, description)
