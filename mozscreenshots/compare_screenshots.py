# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function

import argparse
import glob
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

def get_suffixes(path):
    return [re.sub(r'^[^_]*_', '_', filename)
             for filename in os.listdir(path) if filename.endswith(".png")]


def compare_images(before, after, outdir, similar_dir, args):
    before_trimmed = trim_system_ui("before", before, outdir, args)
    after_trimmed = trim_system_ui("after", after, outdir, args)
    outname = "comparison_" + os.path.basename(before_trimmed)
    outpath = os.path.join(outdir, outname)
    try:
        result = subprocess.call(["compare", "-quiet", "-fuzz", "3%", "-metric", "AE",
                                  before_trimmed, after_trimmed, "null:"],
                                 stderr=subprocess.STDOUT)
    except OSError:
        print("\n\nEnsure that ImageMagick is installed and on your PATH, specifically `compare`.\n")
        raise

    if (result != 0 or args.output_similar_composite):
        subprocess.call(["compare", "-quiet", before_trimmed, after_trimmed, outpath])
    print("\t", end="")
    if result == 0: # same
        print()
        if args.output_similar_composite:
            os.rename(outpath, similar_dir + "/" + outname)
    elif result == 1: # different
        print()
    else:
        print("error")

    # Cleanup intermediate trimmed images
    if os.path.abspath(before) != os.path.abspath(before_trimmed):
        os.remove(before_trimmed)
    if os.path.abspath(after) != os.path.abspath(after_trimmed):
        os.remove(after_trimmed)
    return result


def trim_system_ui(prefix, imagefile, outdir, args):
    if "_fullScreen" in imagefile:
        return imagefile
    outpath = imagefile

    trim_args = []
    if "osx-10-6-" in imagefile:
        titlebar_height = 22 * args.dppx
        chop_top = "0x%d" % titlebar_height
        dock_height = 90 * args.dppx
        chop_bottom = "0x%d" % dock_height
        outpath = outdir + "/chop_" + prefix + "_" + os.path.basename(imagefile)
        trim_args = ["convert", imagefile, "-chop", chop_top, "-gravity", "South", "-chop", chop_bottom, outpath]
    elif "windows7-" in imagefile or "windows8-64-" in imagefile or "windowsxp-" in imagefile:
        taskbar_height = (30 if ("windowsxp-" in imagefile) else 40) * args.dppx
        chop = "0x%d" % taskbar_height
        outpath = outdir + "/chop_" + prefix + "_" + os.path.basename(imagefile)
        trim_args = ["convert", imagefile, "-gravity", "South", "-chop", chop, outpath]
    elif "linux32-" in imagefile or "linux64-" in imagefile:
        titlebar_height = 24 * args.dppx
        chop = "0x%d" % titlebar_height
        outpath = outdir + "/chop_" + prefix + "_" + os.path.basename(imagefile)
        trim_args = ["convert", imagefile, "-chop", chop, outpath]
    else:
        return outpath

    try:
        subprocess.call(trim_args)
    except OSError:
        print("\n\nEnsure that ImageMagick is installed and on your PATH, specifically `convert`.\n")
        raise

    return outpath

def compare_dirs(before, after, outdir, args):
    for before_dirpath, before_dirs, before_files in os.walk(before):
        for before_dir in before_dirs:
            dir_prefix = re.sub(r'-\d{3,}$', '', before_dir)
            matches = glob.glob(os.path.join(after, dir_prefix) + "*")
            if matches and os.path.isdir(matches[0]):
                compare_dirs(os.path.join(before, before_dir), matches[0],
                             os.path.join(outdir, dir_prefix), args)
    print('\nComparing {0} and {1} in {2}'.format(before, after, outdir))
    try:
        os.makedirs(outdir)
    except OSError:
        if not os.path.isdir(outdir):
            print('Error creating directory: %s' % outdir)

    similar_dir = os.path.join(outdir, "similar")
    if args.output_similar_composite:
        os.makedirs(similar_dir)
    sorted_suffixes = sorted(set(get_suffixes(before) + get_suffixes(after)))

    if len(sorted_suffixes) == 0:
        print("No images in the directory")
        return

    maxFWidth = reduce(lambda x, y: max(x, len(y)), sorted_suffixes, 0)

    print("SCREENSHOT SUFFIX".ljust(maxFWidth), "DIFFERING PIXELS (WITH FUZZ)")
    resultDict = defaultdict(list)
    for f in sorted_suffixes:
        image1 = glob.glob(before + "/*" + f)
        image2 = glob.glob(after + "/*" + f)
        if not image1:
            print("{0} exists in after but not in before".format(f))
            resultDict[2].append(f)
            continue
        if not image2:
            print("{0} exists in before but not in after".format(f))
            resultDict[2].append(f)
            continue
        print(f, "", end="".ljust(maxFWidth - len(f)))
        sys.stdout.flush()
        result = compare_images(image1[0], image2[0], outdir, similar_dir, args)
        resultDict[result].append(f)
    print("{0} similar, {1} different, {2} errors".format(len(resultDict[0]), len(resultDict[1]), len(resultDict[2])))

def cli(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='Compare screenshot files or directories for differences')
    parser.add_argument("before", help="Image file or directory of images")
    parser.add_argument("after", help="Image file or directory of images")
    parser.add_argument("--dppx", type=float, default=1.0, help="Scale factor to use for cropping system UI")
    parser.add_argument("--output-similar-composite", action="store_true", help="Output a composite image even when images are 'similar'")

    args = parser.parse_args()

    before = args.before
    after = args.after
    outdir = tempfile.mkdtemp()
    print("Image comparison results:", outdir)

    if (os.path.isdir(before) and os.path.isdir(after)):
        compare_dirs(before, after, outdir, args)
    elif (os.path.isfile(before) and os.path.isfile(after)):
        print()
        compare_images(before, after, outdir, outdir, args)
    else:
        print("Two files or two directories expected")
        return

if __name__ == "__main__":
    cli()
