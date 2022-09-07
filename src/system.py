import taichi as ti
import numpy as np
import pandas as pd


class System:
    def __init__(self, filename):
        self.filename = filename

        self.boundary, self.box, self.head, self.names = self.read_box()
        (
            self.data,
            self.N,
            self.pos,
            self.vel,
        ) = self.read_dump(self.names)

    def read_box(self):
        with open(self.filename) as op:
            file = op.readlines()
        boundary = [1 if i == "pp" else 0 for i in file[4].split()[-3:]]
        box = np.array([i.split()[:2] for i in file[5:8]]).astype(float)
        head = file[:9]
        names = file[8].split()[2:]
        return boundary, box, head, names

    def read_dump(self, names):

        data = pd.read_csv(
            self.filename,
            skiprows=9,
            index_col=False,
            header=None,
            sep=" ",
            names=names,
        )
        N = data.shape[0]

        pos = data[["x", "y", "z"]].values
        vel = data[["vx", "vy", "vz"]].values

        return data, N, pos, vel