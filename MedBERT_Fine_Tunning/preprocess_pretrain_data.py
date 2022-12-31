# lrasmy @ Zhilab 2019/08/10
# This script processes Cerner dataset and builds pickled lists including a full list that includes all patient encounters information
# The output data are (c)pickled, and suitable for training of BERT_EHR models
# Usage: feed this script with patient targets file that include patient_id, encounter_id and other relevant labels field ( here we use mortality, LOS and time to readmit)
# and the main data fields like diagnosis, procedures, medication, ...etc and if you decide to use a predefined vocab file (tokenization/ types dict)
# additionally you can specify sample size , splitting to train,valid,and test sets and the output file path
# So you can run as follow
# python preprocess_pretrain_data.py <data_File>  <types dictionary if available,otherwise use 'NA' to build new one> <output Files Prefix> <data_size>
# Output files:
# <output file>.types: Python dictionary that maps string diagnosis codes to integer indexes
# <output file>.ptencs: List of pts_encs_data
# <output file>.encs: slimmer list that only include tokenized encounter data and labels
# <output file>.bencs: slimmer list that only include tokenized encounter data and labels, along with other list representing segments (visits)
# The above files will also be splitted to train,validation and Test subsets using the Ratio of 7:1:2


import sys
from optparse import OptionParser
import pickle

import numpy as np
import random
import pandas as pd
from datetime import datetime as dt
from datetime import timedelta

# pd.options.mode.chained_assignment = None
# import timeit


### Random split to train ,test and validation sets
def split_fn(pts_ls, pts_sls, outFile):
    print("Splitting")
    dataSize = len(pts_ls)
    np.random.seed(0)
    ind = np.random.permutation(dataSize)
    nTest = int(0.2 * dataSize)
    nValid = int(0.1 * dataSize)
    test_indices = ind[:nTest]
    valid_indices = ind[nTest : nTest + nValid]
    train_indices = ind[nTest + nValid :]

    for subset in ["train", "valid", "test"]:
        if subset == "train":
            indices = train_indices
        elif subset == "valid":
            indices = valid_indices
        elif subset == "test":
            indices = test_indices
        else:
            print("error")
            break
        subset_ptencs = [pts_ls[i] for i in indices]
        subset_ptencs_s = [pts_sls[i] for i in indices]
        ptencsfile = outFile + ".ptencs." + subset
        bertencsfile = outFile + ".bencs." + subset
        pickle.dump(subset_ptencs, open(ptencsfile, "a+b"), -1)
        pickle.dump(subset_ptencs_s, open(bertencsfile, "a+b"), -1)


### Main Function
if __name__ == "__main__":

    # targetFile= sys.argv[1]
    diagFile = sys.argv[1]
    typeFile = sys.argv[2]
    outFile = sys.argv[3]
    p_samplesize = int(sys.argv[4])  ### replace with argparse later

    parser = OptionParser()
    (options, args) = parser.parse_args()

    # _start = timeit.timeit()

    debug = False
    # np.random.seed(1)

    #### Data Loading
    print(" data file")
    data_diag = pd.read_csv(diagFile, sep="\t")
    data_diag.columns = [
        "subject_id",
        "admittime",
        "dischtime",
        "hospital_expire_flag",
        "diagnosis",
        "seq_num",
        "num_prod",
    ]
    if typeFile == "NA":
        types = {"empty_pad": 0}
    else:
        with open(typeFile, "rb") as t2:
            types = pickle.load(t2)

    #### Sampling

    if p_samplesize > 0:
        print("Sampling")
        ptsk_list = data_diag["subject_id"].drop_duplicates()
        pt_list_samp = ptsk_list.sample(n=p_samplesize)
        n_data = data_diag[data_diag["subject_id"].isin(pt_list_samp.values.tolist())]
    else:
        n_data = data_diag

    # n_data.admit_dt_tm.fillna(n_data.discharge_dt_tm, inplace=True) ##, checked the data and no need for that line

    ##### Data pre-processing
    print("Start Data Preprocessing !!!")
    count = 0
    pts_ls = []
    pts_sls = []

    for Pt, group in n_data.groupby("subject_id"):

        pt_encs = []
        time_tonext = []
        #   pt_los=[]
        mort_seq = []
        full_seq = []
        v_seg = []
        pt_discdt = []
        pt_addt = []
        pt_ls = []
        v = 0
        for Time, subgroup in group.sort_values(
            ["seq_num", "num_prod"], ascending=True
        ).groupby(
            "dischtime", sort=False
        ):  ### changing the sort order
            v = v + 1
            diag_l = np.array(subgroup["diagnosis"].drop_duplicates()).tolist()

            if len(diag_l) > 0:
                diag_lm = []
                for code in diag_l:
                    if code in types:
                        diag_lm.append(types[code])
                    else:
                        types[code] = max(types.values()) + 1
                        diag_lm.append(types[code])

                    v_seg.append(v)

                full_seq.extend(diag_lm)

            pt_mort = np.array(
                subgroup["hospital_expire_flag"].drop_duplicates()
            ).tolist()
            print("patients mortality", pt_mort)
            mort_seq.extend(pt_mort)
            print("mortality sequence", mort_seq)
            pt_discdt.append((dt.strptime(Time, "%Y-%m-%d")))
            pt_addt.append(
                dt.strptime(
                    min(np.array(subgroup["admittime"].drop_duplicates()).tolist()),
                    "%Y-%m-%d",
                )
            )

        if len(pt_discdt) > 0:
            for ei, eid in enumerate(pt_discdt):
                print(ei, eid)
                ### updated as I need the time to next encounter not from the previous
                if ei == len(pt_discdt) - 1:
                    enc_td = 0
                else:
                    # enc_td =((dt.strptime(pt_addt[ei+1], '%Y-%m-%d %H:%M:%S'))-(dt.strptime(pt_discdt[ei], '%Y-%m-%d %H:%M:%S'))).days
                    enc_td = (pt_addt[ei + 1] - pt_discdt[ei]).days
                # enc_los=((dt.strptime(pt_addt[ei], '%Y-%m-%d %H:%M:%S'))-(dt.strptime(pt_discdt[ei], '%Y-%m-%d %H:%M:%S'))).days
                # enc_los=(pt_discdt[ei]-pt_addt[ei]).days
            #   time_tonext.append(enc_td)
            #   pt_los.append(enc_los)
            #    pt_ant.append(enc_ant)

            # enc_l=[eid,pt_mort[ei],pt_los[ei],enc_td,diag_l,diag_lm]
            enc_l = [pt_mort, diag_l, diag_lm]
            #   print(enc_ant)
            pt_encs.append(enc_l)
            # all_encs_d[eid]= [pt_mort[ei],pt_los[ei],enc_td,diag_lm] ##  don't need that when we use patient as the unit

        if len(pt_encs) > 0:
            pt_ls.append(pt_encs)

        pts_ls.append(pt_ls)
        pts_sls.append([Pt, mort_seq[-1], full_seq, v_seg])

        count = count + 1

        if count % 1000 == 0:
            print("processed %d pts" % count)

        if count % 100000 == 0:
            print("dumping %d pts" % count)
            split_fn(pts_ls, pts_sls, outFile)
            pts_ls = []
            pts_sls = []

    split_fn(pts_ls, pts_sls, outFile)
    pickle.dump(types, open(outFile + ".types", "wb"), -1)
