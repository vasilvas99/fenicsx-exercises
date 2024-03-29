#!/usr/bin/env python3

import ufl

import numpy as np

from dolfinx import io, mesh
from dolfinx.nls.petsc import NewtonSolver
from dolfinx.fem.petsc import NonlinearProblem
from dolfinx.fem import Function, FunctionSpace

from mpi4py import MPI
from petsc4py import PETSc
from ufl import dot, dx, grad, div

# Define temporal parameters
t = 0  # Start time
T = 10  # Final time
num_steps = 100
dt = (T - t) / num_steps  # time step size

msh = mesh.create_rectangle(
    comm=MPI.COMM_WORLD,
    points=[(0, 0), (64, 64)],
    n=[64, 64],
    cell_type=mesh.CellType.triangle,
)
P1 = ufl.FiniteElement("CG", msh.ufl_cell(), 1)
ME = FunctionSpace(msh, P1)


v = ufl.TestFunction(ME)

u = Function(ME)  # current solution
u0 = Function(ME)  # solution from previous converged step

# zero-out array
u.x.array[:] = 0.0

# i.c.
u.interpolate(lambda x: (np.abs(np.sin(10*x[0]))))

g = u*u/2
lap_g = div(grad(g))
lap_v = div(grad(v))

rhs = - dot(lap_g, lap_v) - dot(grad(u), grad(v)) 
F0 = (
    u * v * dx
    - u0 * v * dx
    - dt * rhs * dx
)

F = F0

problem = NonlinearProblem(F, u)
solver = NewtonSolver(MPI.COMM_WORLD, problem)
solver.convergence_criterion = "incremental"
solver.rtol = 1e-10
solver.max_it = 1000

ksp = solver.krylov_solver
opts = PETSc.Options()
option_prefix = ksp.getOptionsPrefix()
opts[f"{option_prefix}ksp_type"] = "preonly"
opts[f"{option_prefix}pc_type"] = "lu"
ksp.setFromOptions()

file = io.XDMFFile(MPI.COMM_WORLD, "stoyanov-tonchev.xdmf", "w")

file.write_mesh(msh)

u0.x.array[:] = u.x.array
file.write_function(u, t)

while t < T:
    t += dt
    r = solver.solve(u)
    print(f"Step {int(t/dt)}: num iterations: {r[0]}")
    if not r[1]:
        print("Newton iteration failed to converge! Exiting")
        break
    u0.x.array[:] = u.x.array
    file.write_function(u, t)

file.close()
