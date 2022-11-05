import taichi as ti
import numpy as np


@ti.data_oriented
class Calculator:
    """
    使用eam.alloy势函数来计算构型的能量和受力.

    input:
    potential : EAM class
    elements_list : list 指定的元素列表 ['Al', 'Fe'], 列表长度和设定的总atom_type相等.
    init_type_list : ndarray, 每一个原子的元素类别.
    verlet_list, distance_list, neighbor_num : 邻域列表信息.
    pos : ndarray, 原子坐标
    boundary : list, 边界条件
    box : ndarray (3x2), 模拟盒子尺寸

    output:
    energy : ndarray 原子势能
    force : ndarray 原子受力
    """

    def __init__(
        self,
        potential,
        elements_list,
        init_type_list,
        verlet_list,
        distance_list,
        neighbor_number,
        pos,
        boundary,
        box,
    ):

        self.potential = potential
        self.rc = self.potential.rc
        self.elements_list = elements_list
        self.init_type_list = init_type_list
        self.verlet_list = verlet_list
        self.distance_list = distance_list
        self.neighbor_number = neighbor_number
        self.pos = pos
        self.boundary = ti.Vector(boundary)
        self.box = ti.field(dtype=ti.f64, shape=box.shape)
        self.box.from_numpy(box)

    def _get_type_list(self):
        assert len(self.elements_list) == len(
            np.unique(self.init_type_list)
        ), "All type must be assigned."
        for i in self.elements_list:
            assert (
                i in self.potential.elements_list
            ), f"Input element {i} not included in potential."

        init_to_now = np.array(
            [self.potential.elements_list.index(i) for i in self.elements_list]
        )
        N = self.pos.shape[0]
        type_list = np.zeros(N, dtype=int)

        @ti.kernel
        def _get_type_list_real(
            type_list: ti.types.ndarray(),
            N: int,
            init_to_now: ti.types.ndarray(),
            init_type_list: ti.types.ndarray(),
        ):
            for i in range(N):
                type_list[i] = init_to_now[init_type_list[i] - 1] + 1

        _get_type_list_real(type_list, N, init_to_now, self.init_type_list)
        return type_list

    @ti.func
    def pbc(self, rij):
        for i in ti.static(range(rij.n)):
            if self.boundary[i] == 1:
                box_length = self.box[i, 1] - self.box[i, 0]
                rij[i] = rij[i] - box_length * ti.round(rij[i] / box_length)
        return rij

    @ti.kernel
    def _compute_energy_force(
        self,
        verlet_list: ti.types.ndarray(),
        distance_list: ti.types.ndarray(),
        neighbor_number: ti.types.ndarray(),
        atype_list: ti.types.ndarray(),
        dr: float,
        drho: float,
        nr: int,
        nrho: int,
        embedded_data: ti.types.ndarray(),
        phi_data: ti.types.ndarray(),
        elec_density_data: ti.types.ndarray(),
        d_embedded_data: ti.types.ndarray(),
        d_phi_data: ti.types.ndarray(),
        d_elec_density_data: ti.types.ndarray(),
        pos: ti.types.ndarray(element_dim=1),
        energy: ti.types.ndarray(),
        force: ti.types.ndarray(element_dim=1),
        elec_density: ti.types.ndarray(),
        d_embedded_rho: ti.types.ndarray(),
    ):

        N = verlet_list.shape[0]

        for i in range(N):
            i_type = atype_list[i] - 1
            for jj in range(neighbor_number[i]):
                j = verlet_list[i, jj]
                if j > i:
                    j_type = atype_list[j] - 1
                    r = distance_list[i, jj]
                    if r <= self.rc:
                        rk = r / dr
                        k = int(rk)
                        quanzhong = rk - k
                        if k > nr - 2:
                            k = nr - 2

                        pair_enegy = (
                            quanzhong * phi_data[i_type, j_type, k + 1]
                            + (1 - quanzhong) * phi_data[i_type, j_type, k]
                        )
                        energy[i] += pair_enegy / 2.0
                        energy[j] += pair_enegy / 2.0
                        elec_density[i] += (
                            quanzhong * elec_density_data[j_type, k + 1]
                            + (1 - quanzhong) * elec_density_data[j_type, k]
                        )
                        elec_density[j] += (
                            quanzhong * elec_density_data[i_type, k + 1]
                            + (1 - quanzhong) * elec_density_data[i_type, k]
                        )

        for i in range(N):
            i_type = atype_list[i] - 1
            rk = elec_density[i] / drho
            k = int(rk)
            quanzhong = rk - k
            if k > nrho - 2:
                k = nrho - 2
            energy[i] += (
                quanzhong * embedded_data[i_type, k + 1]
                + (1 - quanzhong) * embedded_data[i_type, k]
            )
            d_embedded_rho[i] = (
                quanzhong * d_embedded_data[i_type, k + 1]
                + (1 - quanzhong) * d_embedded_data[i_type, k]
            )

        for i in range(N):
            i_type = atype_list[i] - 1
            for jj in range(neighbor_number[i]):
                j = verlet_list[i, jj]
                if j > i:
                    rij = self.pbc(pos[i] - pos[j])
                    j_type = atype_list[j] - 1
                    r = distance_list[i, jj]
                    if r <= self.rc:
                        rk = r / dr
                        k = int(rk)
                        quanzhong = rk - k
                        if k > nr - 2:
                            k = nr - 2

                        d_pair = (
                            quanzhong * d_phi_data[i_type, j_type, k + 1]
                            + (1 - quanzhong) * d_phi_data[i_type, j_type, k]
                        )
                        d_elec_density_i = (
                            quanzhong * d_elec_density_data[j_type, k + 1]
                            + (1 - quanzhong) * d_elec_density_data[j_type, k]
                        )
                        d_elec_density_j = (
                            quanzhong * d_elec_density_data[i_type, k + 1]
                            + (1 - quanzhong) * d_elec_density_data[i_type, k]
                        )
                        d_pair += (
                            d_embedded_rho[i] * d_elec_density_i
                            + d_embedded_rho[j] * d_elec_density_j
                        )

                        force[i] -= d_pair * rij / r
                        force[j] += d_pair * rij / r

    def compute(self):
        N = self.pos.shape[0]
        self.energy = np.zeros(N)
        self.force = np.zeros((N, 3))
        elec_density = np.zeros(N)
        d_embedded_rho = np.zeros(N)

        type_list = self._get_type_list()
        self._compute_energy_force(
            self.verlet_list,
            self.distance_list,
            self.neighbor_number,
            type_list,
            self.potential.dr,
            self.potential.drho,
            self.potential.nr,
            self.potential.nrho,
            self.potential.embedded_data,
            self.potential.phi_data,
            self.potential.elec_density_data,
            self.potential.d_embedded_data,
            self.potential.d_phi_data,
            self.potential.d_elec_density_data,
            self.pos,
            self.energy,
            self.force,
            elec_density,
            d_embedded_rho,
        )


if __name__ == "__main__":
    from lattice_maker import LatticeMaker
    from neighbor import Neighbor
    from potential import EAM
    from time import time

    # ti.init(ti.gpu, device_memory_GB=5.0)
    ti.init(ti.cpu)
    start = time()
    lattice_constant = 4.05
    x, y, z = 50, 50, 50
    FCC = LatticeMaker(lattice_constant, "FCC", x, y, z)
    FCC.compute()
    end = time()
    print(f"Build {FCC.pos.shape[0]} atoms FCC time: {end-start} s.")

    potential = EAM("./example/CoNiFeAlCu.eam.alloy")
    start = time()
    neigh = Neighbor(FCC.pos, FCC.box, potential.rc, max_neigh=100)
    neigh.compute()
    end = time()
    print(f"Build neighbor time: {end-start} s.")

    start = time()
    Cal = Calculator(
        potential,
        ["Al"],
        np.ones(FCC.pos.shape[0], dtype=np.int32),
        neigh.verlet_list,
        neigh.distance_list,
        neigh.neighbor_number,
        FCC.pos,
        [1, 1, 1],
        FCC.box,
    )
    Cal.compute()
    end = time()
    print(f"Calculate energy and force time: {end-start} s.")
    print("energy:")
    print(Cal.energy[:10])
    print("force:")
    print(Cal.force[:10, :])