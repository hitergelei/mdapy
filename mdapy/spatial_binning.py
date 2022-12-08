# Copyright (c) 2022, mushroomfire in Beijing Institute of Technology
# This file is from the mdapy project, released under the BSD 3-Clause License.

import taichi as ti
import numpy as np
import matplotlib.pyplot as plt
from .plotset import pltset, cm2inch


@ti.data_oriented
class SpatialBinning:
    """
    input:
    pos: (Nx3) ndarray, spatial coordination and the order is x, y and z
    direction : str, binning direction
    1. 'x', 'y', 'z', One-dimensional binning
    2. 'xy', 'xz', 'yz', Two-dimensional binning
    3. 'xyz', Three-dimensional binning
    vbin: ndarray
    1. (N,) ndarray, one value to be binning
    2. (N, 2) ndarray, two values to be binning
    wbin: float, width of each bin, default is 5.
    operation: str, ['mean', 'sum', 'min', 'max'], default is 'mean'
    output:
    res: ndarray
    coor: dict
    """

    def __init__(self, pos, direction, vbin, wbin=5.0, operation="mean") -> None:
        self.pos = pos
        self.N = self.pos.shape[0]
        assert direction in [
            "x",
            "y",
            "z",
            "xy",
            "xz",
            "yz",
            "xyz",
        ], f"unsupported direction {direction}. chosen in ['x', 'y', 'z', 'xy', 'xz', 'yz', 'xyz']"
        self.direction = direction
        assert vbin.shape[0] == self.N, "shpae dismatchs between pos and vbin."
        if vbin.ndim == 1:
            self.vbin = vbin[:, np.newaxis]
        else:
            self.vbin = vbin
        self.wbin = wbin
        assert operation in [
            "mean",
            "sum",
            "min",
            "max",
        ], f"unsupport operation {operation}, chosen in ['mean', 'sum', 'min', 'max']"
        self.operation = operation
        self.if_compute = False

    @ti.kernel
    def Binning_sum(
        self,
        pos: ti.types.ndarray(element_dim=1),
        pos_min: ti.types.ndarray(element_dim=1),
        vbin: ti.types.ndarray(),
        res: ti.types.ndarray(),
    ):

        for i, j in ti.ndrange(self.N, res.shape[-1]):
            cindex = ti.floor((pos[i] - pos_min[0]) / self.wbin, dtype=ti.i32)
            if j == 0:
                res[cindex, 0] += 1.0
            else:
                res[cindex, j] += vbin[i, j - 1]

    @ti.kernel
    def Binning_mean(
        self,
        pos: ti.types.ndarray(element_dim=1),
        pos_min: ti.types.ndarray(element_dim=1),
        vbin: ti.types.ndarray(),
        res: ti.types.ndarray(),
    ):

        for i, j in ti.ndrange(self.N, res.shape[-1]):
            cindex = ti.floor((pos[i] - pos_min[0]) / self.wbin, dtype=ti.i32)
            if j == 0:
                res[cindex, 0] += 1.0
            else:
                res[cindex, j] += vbin[i, j - 1]

        for I in ti.grouped(res):
            if I[I.n - 1] != 0:
                J = I
                J[J.n - 1] = 0
                res[I] /= res[J]

    @ti.kernel
    def Binning_min(
        self,
        pos: ti.types.ndarray(element_dim=1),
        pos_min: ti.types.ndarray(element_dim=1),
        vbin: ti.types.ndarray(),
        res: ti.types.ndarray(),
    ):

        # init res
        for i, j in ti.ndrange(self.N, (1, res.shape[-1])):
            cindex = ti.floor((pos[i] - pos_min[0]) / self.wbin, dtype=ti.i32)
            res[cindex, j] = vbin[i, j - 1]
        # get min
        for i, j in ti.ndrange(self.N, (1, res.shape[-1])):
            cindex = ti.floor((pos[i] - pos_min[0]) / self.wbin, dtype=ti.i32)
            res[cindex, 0] += 1.0
            if vbin[i, j - 1] < res[cindex, j]:
                res[cindex, j] = vbin[i, j - 1]

    @ti.kernel
    def Binning_max(
        self,
        pos: ti.types.ndarray(element_dim=1),
        pos_min: ti.types.ndarray(element_dim=1),
        vbin: ti.types.ndarray(),
        res: ti.types.ndarray(),
    ):

        # init res
        for i, j in ti.ndrange(self.N, (1, res.shape[-1])):
            cindex = ti.floor((pos[i] - pos_min[0]) / self.wbin, dtype=ti.i32)
            res[cindex, j] = vbin[i, j - 1]
        # get max
        for i, j in ti.ndrange(self.N, (1, res.shape[-1])):
            cindex = ti.floor((pos[i] - pos_min[0]) / self.wbin, dtype=ti.i32)
            res[cindex, 0] += 1.0
            if vbin[i, j - 1] > res[cindex, j]:
                res[cindex, j] = vbin[i, j - 1]

    def compute(self):
        xyz2dim = {
            "x": [0],
            "y": [1],
            "z": [2],
            "xy": [0, 1],
            "xz": [0, 2],
            "yz": [1, 2],
            "xyz": [0, 1, 2],
        }
        pos_min = np.min(self.pos, axis=0) - 0.001
        pos_max = np.max(self.pos, axis=0) + 0.001
        pos_delta = pos_max - pos_min
        nbin = np.ceil(pos_delta[xyz2dim[self.direction]] / self.wbin).astype(int)
        self.res = np.zeros((*nbin, self.vbin.shape[1] + 1))
        self.coor = {}
        for i in range(len(self.direction)):
            self.coor[self.direction[i]] = (
                np.arange(self.res.shape[i]) * self.wbin + pos_min[i] + 0.001
            )

        if self.operation == "sum":
            self.Binning_sum(
                self.pos[:, xyz2dim[self.direction]],
                pos_min[xyz2dim[self.direction]][np.newaxis, :],
                self.vbin,
                self.res,
            )
        elif self.operation == "mean":
            self.Binning_mean(
                self.pos[:, xyz2dim[self.direction]],
                pos_min[xyz2dim[self.direction]][np.newaxis, :],
                self.vbin,
                self.res,
            )
        elif self.operation == "min":
            self.Binning_min(
                self.pos[:, xyz2dim[self.direction]],
                pos_min[xyz2dim[self.direction]][np.newaxis, :],
                self.vbin,
                self.res,
            )
        elif self.operation == "max":
            self.Binning_max(
                self.pos[:, xyz2dim[self.direction]],
                pos_min[xyz2dim[self.direction]][np.newaxis, :],
                self.vbin,
                self.res,
            )
        self.if_compute = True

    def plot(self, label_list=None, bar_label=None):
        pltset()
        if not self.if_compute:
            self.compute()

        fig = plt.figure(figsize=(cm2inch(10), cm2inch(7)), dpi=150)
        plt.subplots_adjust(bottom=0.18, top=0.97, left=0.15, right=0.92)
        if len(self.direction) == 1:
            if label_list is not None:
                for i in range(1, self.res.shape[1]):
                    plt.plot(
                        self.coor[self.direction],
                        self.res[:, i],
                        "o-",
                        label=label_list[i - 1],
                    )
                plt.legend()
            else:
                for i in range(1, self.res.shape[1]):
                    plt.plot(self.coor[self.direction], self.res[:, i], "o-")

            plt.xlabel(f"Coordination {self.direction}")
            plt.ylabel(f"Some values")
            ax = plt.gca()
            plt.show()
            return fig, ax
        elif len(self.direction) == 2:
            data = np.zeros(self.res.shape[:2])
            for i in range(self.res.shape[0]):
                for j in range(self.res.shape[1]):
                    data[i, j] = self.res[i, j, 1]

            X, Y = np.meshgrid(
                self.coor[self.direction[0]], self.coor[self.direction[1]]
            )
            h = plt.contourf(X, Y, data.T, cmap="GnBu")
            plt.xlabel(f"Coordination {self.direction[0]}")
            plt.ylabel(f"Coordination {self.direction[1]}")

            ax = plt.gca()
            bar = fig.colorbar(h, ax=ax)
            if bar_label is not None:
                bar.set_label(bar_label)
            else:
                bar.set_label("Some value")
            plt.show()
            return fig, ax
        else:
            raise NotImplementedError(
                "Three-dimensional binning visualization is not supported yet!"
            )


if __name__ == "__main__":
    from lattice_maker import LatticeMaker
    from time import time

    ti.init(ti.cpu)
    FCC = LatticeMaker(4.05, "FCC", 100, 50, 50)
    FCC.compute()
    start = time()
    binning = SpatialBinning(
        FCC.pos,
        "xz",
        FCC.pos[:, 0],
        operation="mean",
    )
    binning.compute()
    end = time()
    print(f"Binning time: {end-start} s.")
    print(binning.res[:, ..., 1].max())
    # print(binning.coor)
    binning.plot(label_list=["x"], bar_label="x")