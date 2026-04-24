import numpy as np
import pandas as pd
from typing import Literal


def get_contigs_idx(ar_input: np.typing.ArrayLike, top_n: int, get_high: bool):
    '''
    get start idx, end idx, and lengths of unbroken runs of 1s/Os
    ar_input is eg df['Status'].map({'HIGH_CONFIDENCE':1, 'LOW_CONFIDENCE':0})
    get_high=True returns 1s, =False 0s
    top_n is num longest contigs to get

    returns 3 arrays
    '''
    a=np.asarray(ar_input, dtype=np.int8)

    change=np.flatnonzero(np.ediff1d(a))+1 # +1 to get correct idx, since ediff1d 'skips' the first elem
    begin=np.empty(change.size+1, dtype=np.uint32) # up to max=4_294_967_295 for 32bits, up to max**2 for uint64 
    end=np.empty(change.size+1, dtype=np.uint32)

    begin[0]=0
    begin[1:]=change
    end[:-1]=change
    end[-1]=a.size

    lens=end-begin 
    vals=a[begin]

    if get_high:
        mask=(vals==1)
    else: mask=(vals==0)

    if top_n>begin.size: # if ask too many contig arrays, just return all we have
        top_n=begin.size

    idx=np.argsort(lens[mask])[-1*top_n:]

    return begin[mask][idx][::-1], end[mask][idx][::-1], lens[mask][idx][::-1]

def rr_to_bpm(rr_ms: np.typing.ArrayLike):
    '''
    convert R-R [ms] array into bpm, error-proof for div by zero and nans
    '''
    rr_ms = np.asarray(rr_ms, dtype=float)
    return np.divide(60_000, rr_ms, out=np.full_like(rr_ms, np.nan), where=(rr_ms!=0))

def bpm_to_rr(bpm: np.typing.ArrayLike):
    '''
    convert bpm array to R-R [ms] array, error-proof for div by zero and nans
    '''
    bpm = np.asarray(bpm, dtype=float)
    return np.divide(60_000, bpm, out=np.full_like(bpm, np.nan), where=(bpm!=0))

def get_mismatchBBI(df_user: pd.DataFrame, top_n: int, shortest_contig: int, get_high: bool, return_corr: bool=False, corr_method: Literal["pearson", "kendall", "spearman"]='spearman'):
    '''
    probbaly would be cool to return time of day info
    '''
    holder=[]
    start,end,lens = get_contigs_idx(ar_input=df_user['Status'].map({'LOW_CONFIDENCE':0, 'HIGH_CONFIDENCE':1}), top_n=top_n, get_high=get_high)
    idx_pick = np.where( lens>=shortest_contig)[0] # todo what if shorest contig we want is shorter than whats available. Then we need to just give everything, except for len=1/2/3 
    #print(len(idx_pick))

    if len(idx_pick) == 0:
        raise ValueError(
            f"No contigs found with length >= {shortest_contig} "
            f"for {'high' if get_high else 'low'} confidence segments."
        )

    times=np.empty(shape=len(idx_pick), dtype=int)

    for i, (start_index, end_index, length) in enumerate(zip(start[idx_pick], end[idx_pick], lens[idx_pick])):
        temp = df_user.iloc[start_index:end_index]
        n_diff_vals= sum(np.ediff1d(temp['timeLocal_ms']) != temp['BBI (ms)'].iloc[1:]) 
        sum_ers_ms= sum(np.abs(np.ediff1d(temp['timeLocal_ms']) -  temp['BBI (ms)'].iloc[1:]))

        times[i] = temp['timeLocal_ms'].iloc[0]

        holder.append([length, n_diff_vals, sum_ers_ms])
    
    if not return_corr:
        df=pd.DataFrame(data=holder, columns=['num measurements', 'num mismatches', 'sum of abs errors'])
        df.insert(0, 'starttime', (pd.to_datetime(times, unit='ms').strftime("%H:%M")))
        df=df.assign(confidence='High' if get_high else 'Low')
    else:
        df=pd.DataFrame(data=holder, columns=['num measurements', 'num mismatches', 'sum of abs errors']).corr(corr_method).round(2)


    return df