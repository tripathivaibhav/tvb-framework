# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and 
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2013, Baycrest Centre for Geriatric Care ("Baycrest")
#
# This program is free software; you can redistribute it and/or modify it under 
# the terms of the GNU General Public License version 2 as published by the Free
# Software Foundation. This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details. You should have received a copy of the GNU General 
# Public License along with this program; if not, you can download it here
# http://www.gnu.org/licenses/old-licenses/gpl-2.0
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#

"""
.. moduleauthor:: Mihai Andrei <mihai.andrei@codemart.ro>
"""
import os
import re
import numpy
from tvb.core.entities.file.files_helper import TvbZip


class ZipSurfaceParser(object):
    """
    Parser for a surface zip.
    Hemispheres are detected if the file name prefixes are the same
    and the suffixes start with: left, right or l, r or lh, rh.
    For example : verticesl.txt and verticesr.txt their uncommon suffixes are l, r
    """
    VERTICES_TOKEN = "vertices"
    NORMALS_TOKEN = "normals"
    TRIANGLES_TOKEN = "triangles"

    LEFT_SUFFIX_RE = re.compile('^(left|lh|l).*')
    "If a vertex file has a suffix matching this it is considered left hemispheric"

    RIGHT_SUFFIX_RE = re.compile('^(right|rh|r).*')

    def __init__(self, path):
        self.bi_hemispheric = False
        self.vertices, self.normals, self.triangles = [], [], []
        self.hemisphere_mask = []
        self._read_vertices = 0

        with TvbZip(path) as self._zipf:
            self._read()


    def _read(self):
        vertices, normals, triangles = self._group_by_type(sorted(self._zipf.namelist()))
        if len(vertices) == 0:
            raise Exception("Cannot find vertices file.")
        if len(vertices) != len(triangles):
            raise Exception("The number of vertices files should be equal to the number of triangles files.")
        if len(normals) != 0 and len(normals) != len(triangles):
            raise Exception("The number of normals files should either be 0 or equal to the numer of triangles files")

        vertices_lh, vertices_rh = self._group_by_hemisph(vertices)
        normals_lh, normals_rh = self._group_by_hemisph(normals)
        triangles_lh, triangles_rh = self._group_by_hemisph(triangles)

        self.bi_hemispheric = (
            len(vertices_lh) == len(vertices_rh) and
            len(normals_lh) == len(normals_rh) and
            len(triangles_lh) == len(triangles_rh)
        )

        if self.bi_hemispheric:
            self._read_files(vertices_lh, normals_lh, triangles_lh)
            vertices_in_lh = self._read_vertices
            self._read_files(vertices_rh, normals_rh, triangles_rh)
            self._stack_arrays()

            self.hemisphere_mask = numpy.ones(len(self.vertices), dtype=numpy.bool)
            self.hemisphere_mask[0:vertices_in_lh] = 0
        else:
            self._read_files(vertices, normals, triangles)
            self._stack_arrays()
            self.hemisphere_mask = numpy.zeros(len(self.vertices), dtype=numpy.bool)


    def _stack_arrays(self):
        self.vertices = numpy.vstack(self.vertices)
        self.triangles = numpy.vstack(self.triangles)
        if self.normals:
            self.normals = numpy.vstack(self.normals)


    def _group_by_type(self, names):
        vertices, normals, triangles = [], [], []

        for name in names:
            if self.VERTICES_TOKEN in name:
                vertices.append(name)
            elif self.NORMALS_TOKEN in name:
                normals.append(name)
            elif self.TRIANGLES_TOKEN in name:
                triangles.append(name)

        return vertices, normals, triangles


    def _group_by_hemisph(self, names):
        """ groups by hemisphere """
        lefts, rights, rest = [], [], []
        prefix_pos = len(os.path.commonprefix(names))

        for name in names:
            suffix = name[prefix_pos:]
            if self.LEFT_SUFFIX_RE.match(suffix):
                lefts.append(name)
            elif self.RIGHT_SUFFIX_RE.match(suffix):
                rights.append(name)
            else:
                rest.append(name)

        if len(rest) != 0 or len(lefts) != len(rights):
            return lefts + rights + rest, []
        else:
            return lefts, rights


    def _read_files(self, vertices_files, normals_files, triangles_files):
        """
        Read vertices, normals and triangles from files.
        All files of a type are concatenated.
        """
        # we need to process vertices in parallel with triangles, so that we can offset triangle indices
        for vertices_file, triangles_file in zip(vertices_files, triangles_files):
            vertices_file = self._zipf.open(vertices_file)
            triangles_file = self._zipf.open(triangles_file)

            current_vertices = numpy.loadtxt(vertices_file, dtype=numpy.float32)
            self.vertices.append(current_vertices)

            current_triangles = numpy.loadtxt(triangles_file, dtype=numpy.int32)
            # offset triangles by amount of previously read vertices
            current_triangles += self._read_vertices
            self.triangles.append(current_triangles)

            self._read_vertices += len(current_vertices)
            vertices_file.close()
            triangles_file.close()

        for normals_file in normals_files:
            normals_file = self._zipf.open(normals_file)

            current_normals = numpy.loadtxt(normals_file, dtype=numpy.float32)
            self.normals.append(current_normals)

            normals_file .close()