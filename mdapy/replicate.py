# Copyright (c) 2022, mushroomfire in Beijing Institute of Technology
# This file is from the mdapy project, released under the BSD 3-Clause License.

import taichi as ti
import numpy as np

try:
    from load_save_data import SaveFile
except Exception:
    from .load_save_data import SaveFile


@ti.data_oriented
class Replicate:
    """This class used to replicate a position with np.ndarray format.

    Args:
        pos (np.ndarray): (:math:`N_p, 3`), initial position to be replicated.
        box (np.ndarray): (:math:`4, 3`), initial system box.
        x (int, optional): replication number (positive integer) along x axis. Defaults to 1.
        y (int, optional): replication number (positive integer) along y axis. Defaults to 1.
        z (int, optional): replication number (positive integer) along z axis. Defaults to 1.
        type_list (np.ndarray, optional): (:math:`N_p`), type for each atom. Defaults to None.

    Outputs:
        - **box** (np.ndarray) - (:math:`4, 3`), replicated box.
        - **pos** (np.ndarray) - (:math:`N, 3`), replicated particle position.
        - **N** (int) - replicated atom number.
        - **type_list** (np.ndarray) - (:math:`N`), replicated type list.

    Examples:
        >>> import mdapy as mp

        >>> mp.init()

        >>> FCC = mp.LatticeMaker(3.615, 'FCC', 10, 10, 10) # Create a FCC structure.

        >>> FCC.compute() # Get atom positions.

        >>> repli = mp.Replicate(FCC.pos, FCC.box, 5, 5, 5) # Initilize a replication class.

        >>> repli.compute() # Get replicated positions.

        >>> repli.pos # Check replicated positions.

        >>> repli.write_data() # Save to DATA file.
    """

    def __init__(self, pos, box, x=1, y=1, z=1, type_list=None):
        if pos.dtype != np.float64:
            pos = pos.astype(np.float64)
        if box.dtype != np.float64:
            box = box.astype(np.float64)
        self.old_pos = pos
        if box.shape == (3, 2):
            self.old_box = np.zeros((4, 3), dtype=box.dtype)
            self.old_box[0, 0], self.old_box[1, 1], self.old_box[2, 2] = (
                box[:, 1] - box[:, 0]
            )
            self.old_box[-1] = box[:, 0]
        elif box.shape == (4, 3) or box.shape == (3, 3):
            assert box[0, 1] == box[0, 2] == box[1, 2] == 0
            if box.shape == (4, 3):
                self.old_box = box
            else:
                self.old_box = np.zeros((4, 3), dtype=box.dtype)
                self.old_box[:-1] = box
        assert x > 0 and isinstance(x, int), "x should be a positive integer."
        self.x = x
        assert y > 0 and isinstance(y, int), "y should be a positive integer."
        self.y = y
        assert z > 0 and isinstance(z, int), "z should be a positive integer."
        self.z = z
        self.old_type_list = type_list
        self.if_computed = False

    @ti.kernel
    def _compute(
        self,
        old_pos: ti.types.ndarray(element_dim=1),
        old_box: ti.types.ndarray(element_dim=1),
        pos: ti.types.ndarray(element_dim=1),
    ):
        N = old_pos.shape[0]
        a = self.y * self.z * N
        b = self.z * N
        for i, j, k, m in ti.ndrange(self.x, self.y, self.z, N):
            pos[i * a + j * b + k * N + m] = (
                old_pos[m] + i * old_box[0] + j * old_box[1] + k * old_box[2]
            )

    @ti.kernel
    def _compute_with_type_list(
        self,
        old_pos: ti.types.ndarray(element_dim=1),
        old_box: ti.types.ndarray(element_dim=1),
        pos: ti.types.ndarray(element_dim=1),
        old_type_list: ti.types.ndarray(),
        type_list: ti.types.ndarray(),
    ):
        N = old_pos.shape[0]
        a = self.y * self.z * N
        b = self.z * N
        for i, j, k, m in ti.ndrange(self.x, self.y, self.z, N):
            index = i * a + j * b + k * N + m
            pos[index] = old_pos[m] + i * old_box[0] + j * old_box[1] + k * old_box[2]
            type_list[index] = old_type_list[m]

    def compute(self):
        """Do the real replicate calculation."""
        self.pos = np.zeros(
            (self.x * self.y * self.z * self.old_pos.shape[0], 3),
            dtype=self.old_pos.dtype,
        )
        if self.old_type_list is None:
            self.type_list = None
            self._compute(self.old_pos, self.old_box, self.pos)
        else:
            assert len(self.old_type_list) == self.old_pos.shape[0]
            self.type_list = np.zeros(self.pos.shape[0], int)
            self._compute_with_type_list(
                self.old_pos,
                self.old_box,
                self.pos,
                np.array(self.old_type_list),
                self.type_list,
            )
        self.box = self.old_box.copy()
        self.box[0] *= self.x
        self.box[1] *= self.y
        self.box[2] *= self.z
        self.if_computed = True

    @property
    def N(self):
        """The particle number."""
        if not self.if_computed:
            self.compute()
        return self.pos.shape[0]

    def write_data(self, output_name=None, data_format="atomic"):
        """This function writes position into a DATA file.

        Args:
            output_name (str, optional): filename of generated DATA file.
            data_format (str, optional): data format, selected in ['atomic', 'charge']
        """
        if not self.if_computed:
            self.compute()

        if output_name is None:
            output_name = f"{self.x}-{self.y}-{self.z}.data"
        if self.type_list is None:
            self.type_list = np.ones(self.N, int)
        SaveFile.write_data(
            output_name,
            self.box,
            [1, 1, 1],
            pos=self.pos,
            type_list=self.type_list,
            data_format=data_format,
        )

    def write_dump(self, output_name=None):
        """This function writes position into a DUMP file.

        Args:
            output_name (str, optional): filename of generated DUMP file.
        """
        if not self.if_computed:
            self.compute()

        if output_name is None:
            output_name = f"{self.x}-{self.y}-{self.z}.dump"
        if self.type_list is None:
            self.type_list = np.ones(self.N, int)

        SaveFile.write_dump(
            output_name, self.box, [1, 1, 1], pos=self.pos, type_list=self.type_list
        )


if __name__ == "__main__":
    ti.init()

    from lattice_maker import LatticeMaker

    fcc = LatticeMaker(3.615, "FCC", 1, 1, 1)
    fcc.compute()
    print(f"build {fcc.N} atoms...")

    repli = Replicate(fcc.pos - 10, fcc.box, 2, 2, 2, type_list=[1, 2, 1, 2])
    repli.compute()
    print(f"replicate {repli.x} {repli.y} {repli.z}...")
    print(repli.box)
    print(repli.type_list)
    # repli.write_data()
    # repli.write_dump()
