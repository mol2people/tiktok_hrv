import numpy as np
import pandas as pd
from typing import Literal
from numpy.typing import ArrayLike, NDArray


def get_contigs_idx(
    ar_input: ArrayLike, top_n: int, get_high: bool
) -> tuple[NDArray[np.uint32], NDArray[np.uint32], NDArray[np.uint32]]:
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

def rr_to_bpm(rr_ms: ArrayLike) -> NDArray[np.float64]:
    '''
    convert R-R [ms] array into bpm, error-proof for div by zero and nans
    '''
    rr_ms = np.asarray(rr_ms, dtype=float)
    return np.divide(60_000, rr_ms, out=np.full_like(rr_ms, np.nan), where=(rr_ms!=0))

def bpm_to_rr(bpm: ArrayLike) -> NDArray[np.float64]:
    '''
    convert bpm array to R-R [ms] array, error-proof for div by zero and nans
    '''
    bpm = np.asarray(bpm, dtype=float)
    return np.divide(60_000, bpm, out=np.full_like(bpm, np.nan), where=(bpm!=0))

def get_mismatchBBI(
    df_user: pd.DataFrame,
    top_n: int,
    shortest_contig: int,
    get_high: bool,
    return_corr: bool = False,
    use_fast: bool = False,
    corr_method: Literal["pearson", "kendall", "spearman"] = 'spearman',
) -> pd.DataFrame:
    '''
    use_fast is vectorized, but cannot return single HIGH/LOW conf elements. For smaller top_n loopy version is preferred
    todo what if shorest contig we want is shorter than whats available. Then we need to just give everything, except for len=1/2 
    '''
    holder=[]
    start,end,lens = get_contigs_idx(ar_input=df_user['Status'].map({'LOW_CONFIDENCE':0, 'HIGH_CONFIDENCE':1}), top_n=top_n, get_high=get_high)
    idx_pick = np.where( lens>=shortest_contig)[0] 

    if len(idx_pick) == 0:
        raise ValueError(
            f"No contigs found with length >= {shortest_contig} "
            f"for {'high' if get_high else 'low'} confidence segments."
        )

    times=np.empty(shape=len(idx_pick), dtype=int)

    if not use_fast:
        for i, (start_index, end_index, length) in enumerate(zip(start[idx_pick], end[idx_pick], lens[idx_pick])):
            temp = df_user.iloc[start_index:end_index]
            n_diff_vals= sum(np.ediff1d(temp['timeLocal_ms']) != temp['BBI (ms)'].iloc[1:]) 
            sum_ers_ms= sum(np.abs(np.ediff1d(temp['timeLocal_ms']) -  temp['BBI (ms)'].iloc[1:]))

            times[i] = temp['timeLocal_ms'].iloc[0]

            holder.append([length, n_diff_vals, sum_ers_ms])
    else:
        time_ms=df_user['timeLocal_ms'].to_numpy(copy=False)
        bbi_ms=df_user['BBI (ms)'].to_numpy(copy=False)
        dt=np.ediff1d(time_ms)
        diff_flag=(dt != bbi_ms[1:]).astype(int)
        abs_err=np.abs(dt - bbi_ms[1:])
        cs_diff=np.concatenate(([0], np.cumsum(diff_flag)))
        cs_err=np.concatenate(([0], np.cumsum(abs_err)))

        start_pick=start[idx_pick]
        end_pick=end[idx_pick]
        len_pick=lens[idx_pick]

        n_diff_vals=np.zeros(shape=len(idx_pick), dtype=int)
        sum_ers_ms=np.zeros(shape=len(idx_pick), dtype=abs_err.dtype)
        mask=len_pick>=2  # fast path indexes transitions, not rows; len<2 contigs contain 0 transitions


        n_diff_vals[mask]=cs_diff[end_pick[mask]-1] - cs_diff[start_pick[mask]]
        sum_ers_ms[mask]=cs_err[end_pick[mask]-1] - cs_err[start_pick[mask]]
        times[:]=time_ms[start_pick]

        for length, n_diff, sum_err in zip(len_pick, n_diff_vals, sum_ers_ms):
            holder.append([length, n_diff, sum_err])
    
    if not return_corr:
        df=pd.DataFrame(data=holder, columns=['vals_per_contig', 'mismatches_per_contig', 'sum_errors_ms'])
        df.insert(0, 'time', (pd.to_datetime(times, unit='ms').strftime("%H:%M")))
        df=df.assign(confidence='High' if get_high else 'Low')
    else:
        df=pd.DataFrame(data=holder, columns=['vals_per_contig', 'mismatches_per_contig', 'sum_errors_ms']).corr(corr_method).round(2)


    return df
