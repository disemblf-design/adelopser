"""Apple Music API 响应数据模型 — 对应原 Go structs"""

from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── 通用嵌套结构 ───────────────────────────────────────────────

class Artwork(BaseModel):
    width: int = 0
    height: int = 0
    url: str = ""
    bg_color: str = Field(default="", alias="bgColor")
    text_color1: str = Field(default="", alias="textColor1")
    text_color2: str = Field(default="", alias="textColor2")
    text_color3: str = Field(default="", alias="textColor3")
    text_color4: str = Field(default="", alias="textColor4")

    class Config:
        populate_by_name = True


class PlayParams(BaseModel):
    id: str = ""
    kind: str = ""

    class Config:
        populate_by_name = True


class Preview(BaseModel):
    url: str = ""


class EditorialVideo(BaseModel):
    motion_square: dict = Field(default_factory=dict, alias="motionDetailSquare")
    motion_tall: dict = Field(default_factory=dict, alias="motionDetailTall")

    class Config:
        populate_by_name = True


class RelationshipData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: dict = Field(default_factory=dict)


class RelationshipList(BaseModel):
    href: str = ""
    data: list[RelationshipData] = Field(default_factory=list)


class Relationships(BaseModel):
    tracks: RelationshipList = Field(default_factory=RelationshipList)
    artists: RelationshipList = Field(default_factory=RelationshipList)
    albums: RelationshipList = Field(default_factory=RelationshipList)


# ─── Track 数据 ──────────────────────────────────────────────────

class ExtendedAssetUrls(BaseModel):
    enhanced_hls: str = Field(default="", alias="enhancedHls")

    class Config:
        populate_by_name = True


class TrackAttributes(BaseModel):
    artist_name: str = Field(default="", alias="artistName")
    url: str = ""
    disc_number: int = Field(default=0, alias="discNumber")
    genre_names: list[str] = Field(default_factory=list, alias="genreNames")
    extended_asset_urls: ExtendedAssetUrls = Field(
        default_factory=ExtendedAssetUrls, alias="extendedAssetUrls"
    )
    has_time_synced_lyrics: bool = Field(default=False, alias="hasTimeSyncedLyrics")
    is_mastered_for_itunes: bool = Field(default=False, alias="isMasteredForItunes")
    is_apple_digital_master: bool = Field(default=False, alias="isAppleDigitalMaster")
    content_rating: str = Field(default="", alias="contentRating")
    duration_in_millis: int = Field(default=0, alias="durationInMillis")
    release_date: str = Field(default="", alias="releaseDate")
    name: str = ""
    isrc: str = ""
    audio_traits: list[str] = Field(default_factory=list, alias="audioTraits")
    has_lyrics: bool = Field(default=False, alias="hasLyrics")
    album_name: str = Field(default="", alias="albumName")
    play_params: PlayParams = Field(default_factory=PlayParams, alias="playParams")
    track_number: int = Field(default=0, alias="trackNumber")
    audio_locale: str = Field(default="", alias="audioLocale")
    composer_name: str = Field(default="", alias="composerName")
    artwork: Artwork = Field(default_factory=Artwork)
    previews: list[Preview] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class TrackRespData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: TrackAttributes = Field(default_factory=TrackAttributes)
    relationships: Relationships = Field(default_factory=Relationships)


class TrackResp(BaseModel):
    href: str = ""
    next: str = ""
    data: list[TrackRespData] = Field(default_factory=list)


# ─── Song 数据 ───────────────────────────────────────────────────

class SongAttributes(TrackAttributes):
    """Song 属性与 Track 几乎相同，额外字段"""
    pass


class SongRespData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: SongAttributes = Field(default_factory=SongAttributes)
    relationships: Relationships = Field(default_factory=Relationships)


class SongResp(BaseModel):
    href: str = ""
    next: str = ""
    data: list[SongRespData] = Field(default_factory=list)


# ─── Album 数据 ──────────────────────────────────────────────────

class AlbumAttributes(BaseModel):
    artist_name: str = Field(default="", alias="artistName")
    artwork: Artwork = Field(default_factory=Artwork)
    genre_names: list[str] = Field(default_factory=list, alias="genreNames")
    is_compilation: bool = Field(default=False, alias="isCompilation")
    is_complete: bool = Field(default=False, alias="isComplete")
    is_mastered_for_itunes: bool = Field(default=False, alias="isMasteredForItunes")
    is_apple_digital_master: bool = Field(default=False, alias="isAppleDigitalMaster")
    is_prerelease: bool = Field(default=False, alias="isPrerelease")
    is_single: bool = Field(default=False, alias="isSingle")
    name: str = ""
    play_params: PlayParams = Field(default_factory=PlayParams, alias="playParams")
    release_date: str = Field(default="", alias="releaseDate")
    track_count: int = Field(default=0, alias="trackCount")
    upc: str = ""
    url: str = ""
    content_rating: str = Field(default="", alias="contentRating")
    copyright: str = ""
    record_label: str = Field(default="", alias="recordLabel")
    editorial_video: dict = Field(default_factory=dict, alias="editorialVideo")

    class Config:
        populate_by_name = True


class AlbumRespData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: AlbumAttributes = Field(default_factory=AlbumAttributes)
    relationships: Relationships = Field(default_factory=Relationships)


class AlbumResp(BaseModel):
    href: str = ""
    next: str = ""
    data: list[AlbumRespData] = Field(default_factory=list)


# ─── Playlist 数据 ───────────────────────────────────────────────

class PlaylistAttributes(BaseModel):
    artwork: Artwork = Field(default_factory=Artwork)
    artist_name: str = Field(default="", alias="artistName")
    is_apple_digital_master: bool = Field(default=False, alias="isAppleDigitalMaster")
    is_mastered_for_itunes: bool = Field(default=False, alias="isMasteredForItunes")
    content_rating: str = Field(default="", alias="contentRating")
    name: str = ""
    play_params: PlayParams = Field(default_factory=PlayParams, alias="playParams")
    url: str = ""
    editorial_video: dict = Field(default_factory=dict, alias="editorialVideo")

    class Config:
        populate_by_name = True


class PlaylistRespData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: PlaylistAttributes = Field(default_factory=PlaylistAttributes)
    relationships: Relationships = Field(default_factory=Relationships)


class PlaylistResp(BaseModel):
    href: str = ""
    next: str = ""
    data: list[PlaylistRespData] = Field(default_factory=list)


# ─── Station 数据 ────────────────────────────────────────────────

class StationRespData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: dict = Field(default_factory=dict)


class StationResp(BaseModel):
    href: str = ""
    next: str = ""
    data: list[StationRespData] = Field(default_factory=list)


# ─── Music Video 数据 ────────────────────────────────────────────

class MVAttributes(BaseModel):
    artist_name: str = Field(default="", alias="artistName")
    artwork: Artwork = Field(default_factory=Artwork)
    name: str = ""
    url: str = ""
    play_params: PlayParams = Field(default_factory=PlayParams, alias="playParams")

    class Config:
        populate_by_name = True


class MVRespData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: MVAttributes = Field(default_factory=MVAttributes)


class MVResp(BaseModel):
    href: str = ""
    next: str = ""
    data: list[MVRespData] = Field(default_factory=list)


# ─── Search 数据 ─────────────────────────────────────────────────

class ArtistSearchData(BaseModel):
    id: str = ""
    type: str = ""
    href: str = ""
    attributes: dict = Field(default_factory=dict)


class SongResults(BaseModel):
    href: str = ""
    next: str = ""
    data: list[SongRespData] = Field(default_factory=list)


class AlbumResults(BaseModel):
    href: str = ""
    next: str = ""
    data: list[AlbumRespData] = Field(default_factory=list)


class ArtistResults(BaseModel):
    href: str = ""
    next: str = ""
    data: list[ArtistSearchData] = Field(default_factory=list)


class SearchResults(BaseModel):
    songs: Optional[SongResults] = None
    albums: Optional[AlbumResults] = None
    artists: Optional[ArtistResults] = None

    class Config:
        populate_by_name = True


class SearchResp(BaseModel):
    results: SearchResults = Field(default_factory=SearchResults)


# ─── 下载任务模型 ────────────────────────────────────────────────

class Counter(BaseModel):
    """下载计数器"""
    unavailable: int = 0
    not_song: int = 0
    error: int = 0
    success: int = 0
    total: int = 0


class AddedTrack(BaseModel):
    """已下载音轨记录"""
    path: str = ""
    artist: str = ""
    artist_id: str = Field(default="", alias="artistID")
    album: str = ""
    song: str = ""

    class Config:
        populate_by_name = True
