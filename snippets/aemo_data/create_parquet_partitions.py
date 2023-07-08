# Python script (executable via CLI) to create parquet partitions
# for large AEMO data CSVs. Assumes first line is table header and that only one table
# type is in the file
#
# Copyright (C) 2023 Abhijith Prakash
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import logging

import pandas as pd

from pathlib import Path
from tqdm import tqdm


def arg_parser():
    description = (
        "Chunk large monthly AEMO data table CSVs into parquet partitions. "
        + "Assumes that the table header is in the 2nd row"
    )
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-file", type=str, required=True, help=("File to process. Must be CSV")
    )
    parser.add_argument(
        "-output_dir",
        type=str,
        required=True,
        help=(
            "Directory to write parquet chunks to. Will be created if it does not exist"
        ),
    )
    parser.add_argument(
        "-chunksize",
        type=int,
        default=10**6,
        help=("Size of each DataFrame chunk (# of lines). Default 10^6"),
    )
    args = parser.parse_args()
    return args


def get_columns(file_path: Path) -> pd.Index:
    col_df = pd.read_csv(file_path, header=1, nrows=0)
    return col_df.columns


def estimate_size_of_lines(file_path: Path, columns=pd.Index) -> float:
    sample_size = 1000
    sample = pd.read_csv(file_path, skiprows=2, nrows=sample_size, header=None)
    sample.columns = columns
    total_size = sample.memory_usage().sum()
    size_per_line = total_size / len(sample)
    return size_per_line


def chunk_file(file_path: Path, output_dir: Path, chunksize: int) -> None:
    if not file_path.suffix.lower() == ".csv":
        logging.error("File is not a CSV")
        exit()
    cols = get_columns(file_path)
    size_per_line = estimate_size_of_lines(file_path, cols)
    file_size = file_path.stat().st_size
    file_stem = file_path.stem
    with pd.read_csv(file_path, chunksize=chunksize, skiprows=2, header=None) as reader:
        with tqdm(total=file_size, desc="Progress estimate based on file size") as pbar:
            for i, chunk in enumerate(reader):
                chunk.columns = cols
                out_file = Path(file_stem + f"_chunk{i}.parquet")
                chunk.to_parquet(output_dir / out_file)
                # See here for comparison of pandas DataFrame size vs CSV size:
                # https://stackoverflow.com/questions/18089667/how-to-estimate-how-much-memory-a-pandas-dataframe-will-need#32970117
                pbar.update((size_per_line * chunksize) / 2)


def main():
    logging.basicConfig(format="\n%(levelname)s:%(message)s", level=logging.INFO)
    args = arg_parser()
    f = Path(args.file)
    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    elif len(sorted(output_dir.glob(f.stem + "*.parquet"))) > 1:
        logging.error("Pre-existing chunks of this file in output directory. Exiting.")
        exit()
    if not f.exists():
        logging.error("Path does not exist")
        exit()
    if not f.is_file():
        logging.error("Path provided does not point to a file")
        exit()
    chunk_file(f, output_dir, args.chunksize)


if __name__ == "__main__":
    main()
