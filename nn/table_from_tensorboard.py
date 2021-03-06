import tensorflow as tf
from collections import defaultdict
import numpy
import pandas
import sys
import glob
from pathlib import Path


def box_filt(n):
    return numpy.array([1] * n, dtype="float32") / n


def do_single(path: Path):
    [path] = path.glob("events.out.*")
    print(path)
    avg_width = 50

    values = defaultdict(list)
    
    for e in tf.train.summary_iterator(str(path)):
        for v in e.summary.value:
            if v.tag.startswith("val_") and v.tag != "val_loss" and not v.image.width and not (v.tag.startswith("val_rel_error") and not v.tag.endswith("_kcal")):
                values[v.tag] += [v.simple_value]

    table = {}

    for k, v in sorted(values.items(), key=lambda i: "A" if i[0] == "val_rel_error_kcal" else "B"):
        v = numpy.asarray(v)
        bf = box_filt(avg_width)
        v_filt = numpy.convolve(v, bf, mode='valid')
        #print(v_filt)
        table[k] = min(v_filt)
    return table


def run_name(path):
    return Path(path).name

all_data = {run_name(run): do_single(Path(run)) for run in sys.argv[1:]}

df = pandas.DataFrame.from_dict(all_data, orient='index')
print(df)
print(df.to_latex(float_format="{:.3g}".format))