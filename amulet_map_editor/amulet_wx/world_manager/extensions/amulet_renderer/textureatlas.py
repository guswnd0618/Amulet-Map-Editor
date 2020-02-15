#!/usr/bin/env python
#
# Copyright (c) 2014 Matthew Borgerson
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
"""Texture Atlas and Map File Generation Utility Classes"""

from PIL import Image
import numpy
import math
from typing import Dict, Tuple, List, Any
from amulet_map_editor import log

DESCRIPTION = """Packs many smaller images into one larger image, a Texture
Atlas. A companion file (.map), is created that defines where each texture is
mapped in the atlas."""


class AtlasTooSmall(Exception):
    pass


class Packable(object):
    """A two-dimensional object with position information."""

    def __init__(self, width, height):
        self._x = 0
        self._y = 0
        self._width = width
        self._height = height

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = value

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        self._y = value

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def perimeter(self):
        return 2*self._width + 2*self._height


class PackRegion(object):
    """A region that two-dimensional Packable objects can be packed into."""

    def __init__(self, x, y, width, height):
        """Constructor."""
        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self._sub1 = None
        self._sub2 = None
        self._packable = None

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def packable(self):
        return self._packable

    def get_all_packables(self):
        """Returns a list of all Packables in this region and sub-regions."""
        if self._packable:
            return [self._packable] + self._sub1.get_all_packables() + \
                                      self._sub2.get_all_packables()
        return []

    def pack(self, packable):
        """Pack 2D packable into this region."""
        if not self._packable:
            # Is there room to pack this?
            if (packable.width > self._width) or \
               (packable.height > self._height):
                return False

            # Pack
            self._packable = packable

            # Set x, y on Packable
            self._packable.x = self._x
            self._packable.y = self._y

            # Create sub-regions
            self._sub1 = PackRegion(self._x,
                                    self._y+self._packable.height,
                                    self._packable.width,
                                    self._height-self._packable.height)
            self._sub2 = PackRegion(self._x+self._packable.width,
                                    self._y,
                                    self._width-self._packable.width,
                                    self._height)
            return True

        # Pack into sub-region
        return self._sub1.pack(packable) or self._sub2.pack(packable)


class Frame(Packable):
    """An image file that can be packed into a PackRegion."""

    def __init__(self, filename):
        self._filename = filename

        # Determine frame dimensions
        self._image = Image.open(filename)
        width, height = self._image.size

        super(Frame, self).__init__(width, height)

    @property
    def filename(self):
        return self._filename

    def draw(self, image):
        """Draw this frame into another Image."""
        image.paste(self._image, (self.x, self.y))


class Texture(object):
    """A collection of one or more frames."""

    def __init__(self, name, frames):
        self._name = name
        self._frames = frames

    @property
    def name(self):
        return self._name

    @property
    def frames(self):
        return self._frames


class TextureAtlas(PackRegion):
    """Texture Atlas generator."""

    def __init__(self, width, height):
        super(TextureAtlas, self).__init__(0, 0, width, height)
        self._textures = []

    @property
    def textures(self) -> List[Texture]:
        return self._textures

    def pack(self, texture):
        """Pack a Texture into this atlas."""
        self._textures.append(texture)
        for frame in texture.frames:
            if not super(TextureAtlas, self).pack(frame):
                raise AtlasTooSmall('Failed to pack frame %s' % frame.filename)

    def to_dict(self) -> Dict[str, Tuple[int, int, int, int]]:
        return {
            tex.name: (
                tex.frames[0].x/self.width,
                tex.frames[0].y/self.height,
                (tex.frames[0].x+tex.frames[0].width)/self.width,
                (tex.frames[0].y+min(tex.frames[0].height, tex.frames[0].width))/self.height
            ) for tex in self.textures
        }

    def generate(self, mode):
        """Generates the final texture atlas."""
        out = Image.new(mode, (self.width, self.height))
        for t in self._textures:
            for f in t.frames:
                f.draw(out)
        return out

    def write(self, filename, mode):
        """Generates and saves the final texture atlas."""
        out = self.generate(mode)
        out.save(filename)


class TextureAtlasMap(object):
    """Texture Atlas Map file generator."""

    def __init__(self, atlas):
        self._atlas = atlas

    def write(self, fd):
        """Writes the texture atlas map file into file object fd."""
        raise Exception('Not Implemented')


def create_atlas(texture_dict: Dict[Any, str]) -> Tuple[numpy.ndarray, Dict[Any, Tuple[float, float, float, float]], int, int]:
    log.info('Creating texture atlas')
    # Parse texture names
    textures = []
    for texture in texture_dict.values():
        # Look for a texture name
        name, frames = texture, [texture]

        # Build frame objects
        frames = [Frame(f) for f in frames]

        # Add frames to texture object list
        textures.append(Texture(name, frames))

    # Sort textures by perimeter size in non-increasing order
    textures = sorted(textures, key=lambda i: i.frames[0].perimeter, reverse=True)

    height = 0
    width = 0
    pixels = 0
    for t in textures:
        for f in t.frames:
            height = max(f.height, height)
            width = max(f.width, width)
            pixels += f.height * f.width

    size = max(
        height,
        width,
        1 << (math.ceil(pixels ** 0.5) - 1).bit_length()
    )

    atlas_created = False
    atlas = None
    while not atlas_created:
        try:
            # Create the atlas and pack textures in
            log.info(f'Trying to pack textures into image of size {size}x{size}')
            atlas = TextureAtlas(size, size)

            for texture in textures:
                atlas.pack(texture)
            atlas_created = True
        except AtlasTooSmall:
            log.info(f'Image was too small. Trying with a larger area')
            size *= 2

    log.info('Successfully packed textures into an image of size {size}x{size}')

    texture_atlas = numpy.array(atlas.generate('RGBA'), numpy.uint8).ravel()

    texture_bounds = atlas.to_dict()
    texture_bounds = {tex_id: texture_bounds[texture_path] for tex_id, texture_path in texture_dict.items()}

    log.info('Finished creating texture atlas')
    return texture_atlas, texture_bounds, atlas.width, atlas.height
