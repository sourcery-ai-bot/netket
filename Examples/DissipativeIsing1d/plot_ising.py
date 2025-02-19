import numpy as np
import matplotlib.pyplot as plt
import json

plt.ion()

# N=20
exact = 0.0

# N=80
# exact=-1.273321360724e+00*80

while True:
    plt.clf()
    plt.ylabel("LdagL")
    plt.xlabel("Iteration #")

    data = json.load(open("test.log"))
    iters = data["LdagL"]["iters"]
    energy = data["LdagL"]["Mean"]
    sigma = data["LdagL"]["Sigma"]
    evar = data["LdagL"]["Variance"]

    nres = len(iters)
    cut = nres
    if cut > cut:
        fitx = iters[-cut:-1]
        fity = energy[-cut:-1]
        z = np.polyfit(fitx, fity, deg=0)
        p = np.poly1d(z)

        plt.xlim([0, cut])
        maxval = np.max(energy[-cut:-1])
        plt.ylim([exact - (np.abs(exact) * 0.01), maxval + np.abs(maxval) * 0.01])
        error = (z[0] - exact) / -exact
        plt.gca().text(
            0.95,
            0.8,
            f"Relative Error : {error:.2e}",
            verticalalignment="bottom",
            horizontalalignment="right",
            color="green",
            fontsize=15,
            transform=plt.gca().transAxes,
        )

        plt.plot(fitx, p(fitx))

    plt.errorbar(iters, energy, yerr=sigma, color="red")
    plt.axhline(y=exact, xmin=0, xmax=iters[-1], linewidth=2, color="k", label="Exact")

    if energy[-1] < 0.1:
        plt.yscale("log")

    plt.legend(frameon=False)
    plt.pause(10)
    plt.show()

plt.ioff()
plt.show()
