import cv2
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def serialize_frame(frame, encode='*.png'):
    return cv2.imencode(encode, frame)[1].tostring(None)


def deserialize_frame(string):
    return cv2.imdecode(
        np.fromstring(string, dtype=np.uint8), cv2.CV_LOAD_IMAGE_UNCHANGED)


def read_frames(frames):
    return np.array([deserialize_frame(frame) for frame in frames])


def write_hdf5(filename, data, keys=None):
    store = pd.HDFStore(filename, complevel=9, complib='blosc')
    if keys is None:
        keys = data.keys()
    for key in keys:
        store.put(key, data[key], format='table', append=False)
    store.close()


def read_hdf5(filename, keys=None):
    store = pd.HDFStore(filename)
    if keys is None:
        keys = [key[1:] for key in store.keys()]
    data = {}
    for key in keys:
        data[key] = store.get(key)
    store.close()
    return data


def plot_image(img):
    plt.figure()
    plt.imshow(img, interpolation='none', cmap='jet', vmin=0, vmax=1024)
    plt.show()


def plot_histogram(img):
    plt.figure()
    plt.subplot(211)
    plt.imshow(img, interpolation='none', cmap='jet', vmin=0, vmax=1024)
    plt.subplot(212)
    plt.hist(img.flatten(), 100, range=(0, 1024), fc='k', ec='k')
    plt.xlim(0, 1024)
    plt.show()


def plot_image3d(img):
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    xx, yy = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    ax.plot_surface(xx, yy, img, rstride=1, cstride=1, linewidth=0,
                    cmap='jet', vmin=0, vmax=1024)
    plt.show()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--file', type=str, default=None, help='hdf5 filename')
    parser.add_argument(
        '-t', '--tables', type=str, default=None, nargs='+', help='tables names')
    args = parser.parse_args()

    filename = args.file
    tables = args.tables
    data = read_hdf5(filename, tables)

    if 'robot' in data.keys():
        robot = data['robot']
        from measures.velocity import Velocity
        velocity = Velocity()
        speeds = [velocity.instantaneous(
            robot.time[k], np.array(robot.position[k]))[0]
            for k in range(len(robot))]
        running = [speed > 0.0005 for speed in speeds]
        plt.figure()
        plt.subplot(211)
        plt.plot(speeds)
        plt.subplot(212)
        plt.plot(running)
        plt.show()

    if 'tachyon' in data.keys():
        tachyon = data['tachyon']
        tachyon = tachyon[tachyon.frame.notnull()]
        #frames = read_frames(tachyon.frame)

        if 'minor_axis' in tachyon.columns:
            idx = tachyon.index[tachyon['minor_axis'] > 0]
            idx0, idx1 = idx[0], idx[-1]
            time0 = tachyon.time[idx0]
            time1 = tachyon.time[idx1]
            print idx0, idx1, time0, time1
            idx = tachyon.index[tachyon.time < time0-1]
            idx0 = idx[-1]
            idx = tachyon.index[tachyon.time > time1+1]
            idx1 = idx[0]
            print idx0, idx1
            if idx0 < 0:
                idx0 = 0
            if idx1 > len(tachyon):
                idx1 = len(tachyon)
            meas = tachyon.loc[idx0:idx1]
            time = np.array(meas['time'])

            # Find tracks
            tachyonw = tachyon[tachyon.minor_axis.notnull()]
            laser = np.array(tachyonw['minor_axis'] > 0)
            lasernr = np.append(np.bitwise_not(laser[0]), np.bitwise_not(laser[:-1]))
            lasernl = np.append(np.bitwise_not(laser[1:]), np.bitwise_not(laser[-1]))
            laser_on = np.bitwise_and(laser, lasernr)
            laser_off = np.bitwise_and(laser, lasernl)
            laser_on_idx = tachyonw.index[laser_on]
            laser_off_idx = tachyonw.index[laser_off]
            print laser_on_idx, laser_off_idx
            plt.figure()
            plt.plot(laser_on)
            plt.plot(laser_off)
            plt.show()

            # First track geometry calculation
            from measures.geometry import Geometry
            geometry = Geometry(200)
            ellipses = []
            for frame in tachyon.frame[laser_on_idx[0]:laser_off_idx[0]]:
                img = deserialize_frame(frame)
                ellipse = geometry.find_geometry(img)
                ellipses.append(np.array(ellipse))
            ellipses = np.array(ellipses)
            widths = np.array([axis[1]for axis in ellipses[:, 1]])
            plt.figure()
            plt.subplot(211)
            plt.plot(widths)
            plt.subplot(212)
            plt.plot(widths * 0.375)
            plt.show()

            plot_image(geometry.draw_geometry(img, ellipse))
            plot_image3d(img)  # Show image as 3D surface
            plot_histogram(img)

            # N = len(measures['power'])
            # print measures.loc[N-10:N-1]['time']
            # time = np.array(measures['time'])
            # print np.isclose(time[1:], time[:-1], atol=1e-03, rtol=0)
            tachyonp = tachyon[tachyon.power.notnull()]
            #tachyon.time = tachyon.time - tachyon.time[0]

            plt.figure()
            plt.subplot(211)
            tachyonp.plot(x='time', y='minor_axis',
                          xlim=(time[0], time[-1]), ylim=(0, 5), color='blue')
            plt.subplot(212)
            tachyonp.plot(x='time', y='power',
                          xlim=(time[0], time[-1]), ylim=(0, 1500), color='red')
            plt.show()
