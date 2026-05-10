# -*- coding: utf-8 -*-
# ===============================================================================
# Copyright 2021 An-Jun Liu
# Last Modified Date: 12/28/2021
# ===============================================================================

import os
import numpy as np 
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score
from math import pi
import matplotlib.patches as patches
from scipy.stats import norm
import seaborn as sns; sns.set()
from datetime import date
DEBUG = 1

# ===============================================================================
# CSV format normalization (V2.0 88-col K/Ca → V3.7 98-col Ca/K, in-memory)
# ===============================================================================
def normalize_csv_to_v37(data):
    """Detect V2.0 (88 cols, K/Ca) vs V3.7 (98 cols, Ca/K) and return V3.7-form.

    V2.0 → V3.7 transformations:
      1. col 23-24 K/Ca → Ca/K (1/x with std propagation)
      2. Append 10 isochron cols (88-97) computed from raw Ar component cols
    V3.7 → unchanged.

    Input  : list of CSV lines (with newlines)
    Output : list of CSV lines (V3.7 format)
    """
    if not data:
        return data
    header = data[0].rstrip()
    cols = header.split(',')
    n = len(cols)
    if n == 98 and len(cols) > 23 and cols[23] == 'Ca/K':
        return data  # already V3.7
    if not (n == 88 and len(cols) > 23 and cols[23] == 'K/Ca'):
        return data  # unknown format — pass through

    # Build new V3.7 header
    new_cols = list(cols)
    new_cols[23] = 'Ca/K'
    new_cols[24] = 'Ca/K_std'
    new_cols += [
        'normal isochron', '40Ar(m)/36Ar(m)', '40Ar(m)/36Ar(m)_std',
        '39Ar(m)/36Ar(m)', '39Ar(m)/36Ar(m)_std',
        'inverse isochron', '36Ar(m)/40Ar(m)', '36Ar(m)/40Ar(m)_std',
        '39Ar(m)/40Ar(m)', '39Ar(m)/40Ar(m)_std',
    ]
    new_data = [','.join(new_cols) + '\n']

    def _f(parts, idx):
        try:
            return float(parts[idx])
        except (ValueError, IndexError):
            return 0.0

    for line in data[1:]:
        if not line.strip():
            new_data.append(line)
            continue
        parts = line.rstrip('\n\r').split(',')
        if len(parts) < 88:
            new_data.append(line)
            continue

        # 1. col 23-24 K/Ca → Ca/K
        kca = _f(parts, 23)
        kca_std = _f(parts, 24)
        if kca > 0:
            cak = 1.0 / kca
            cak_std = kca_std / (kca * kca)
        else:
            cak, cak_std = 0.0, 0.0
        parts[23] = repr(cak)
        parts[24] = repr(cak_std)

        # 2. compute isochron sums + ratios from raw Ar components
        ar36_a, ar36_a_s = _f(parts, 26), _f(parts, 27)
        ar36_c, ar36_c_s = _f(parts, 28), _f(parts, 29)
        ar36_ca, ar36_ca_s = _f(parts, 30), _f(parts, 31)
        ar36_cl, ar36_cl_s = _f(parts, 32), _f(parts, 33)
        ar39_k, ar39_k_s = _f(parts, 46), _f(parts, 47)
        ar39_ca, ar39_ca_s = _f(parts, 48), _f(parts, 49)
        ar40_r, ar40_r_s = _f(parts, 50), _f(parts, 51)
        ar40_a, ar40_a_s = _f(parts, 52), _f(parts, 53)
        ar40_c, ar40_c_s = _f(parts, 54), _f(parts, 55)
        ar40_k, ar40_k_s = _f(parts, 56), _f(parts, 57)

        ar36_m = ar36_a + ar36_c + ar36_ca + ar36_cl
        ar36_m_s = (ar36_a_s**2 + ar36_c_s**2 + ar36_ca_s**2 + ar36_cl_s**2) ** 0.5
        ar39_m = ar39_k + ar39_ca
        ar39_m_s = (ar39_k_s**2 + ar39_ca_s**2) ** 0.5
        ar40_m = ar40_r + ar40_a + ar40_c + ar40_k
        ar40_m_s = (ar40_r_s**2 + ar40_a_s**2 + ar40_c_s**2 + ar40_k_s**2) ** 0.5

        def _ratio(num, num_s, den, den_s):
            if den == 0 or num == 0:
                return 0.0, 0.0
            r = num / den
            r_s = abs(r) * ((num_s / num) ** 2 + (den_s / den) ** 2) ** 0.5
            return r, r_s

        r40_36, r40_36_s = _ratio(ar40_m, ar40_m_s, ar36_m, ar36_m_s)
        r39_36, r39_36_s = _ratio(ar39_m, ar39_m_s, ar36_m, ar36_m_s)
        r36_40, r36_40_s = _ratio(ar36_m, ar36_m_s, ar40_m, ar40_m_s)
        r39_40, r39_40_s = _ratio(ar39_m, ar39_m_s, ar40_m, ar40_m_s)

        parts.extend([
            'normal isochron', repr(r40_36), repr(r40_36_s),
            repr(r39_36), repr(r39_36_s),
            'inverse isochron', repr(r36_40), repr(r36_40_s),
            repr(r39_40), repr(r39_40_s),
        ])
        new_data.append(','.join(parts) + '\n')

    return new_data


# Utilities function
def ratioSigma(mu_y, sigma_y, mu_x, sigma_x,ratio):
    return np.sqrt((sigma_y/mu_y)**2 + (sigma_x/mu_x)**2)*ratio

def minusSigma(sigma_x, sigma_y):
    return np.sqrt(sigma_x**2 + sigma_y**2)

# T0 regression fitting functions
# ===============================================================================
def linear(x, a, b):
    return a*x + b

def average(x, a):
    return 0*x + a

fit_func_list = [linear, average]

# functions for button
# ===============================================================================
def calculateT0(fit_function_type, v_t, mask,num):
    """
    Input:
    1. fit_function_type: 0 for linear, 1 for average

    2. v_t: raw voltage-time data

    3. mask: table of selected points

    Output:
    return [status, T0, T0_SIGMA, R^2]

    status: 
    0 success

    1 failed at fitting data from which the outliers are removed
    
    """

    # initialization
    T0 = np.zeros(5)
    T0_SIGMA = np.zeros(5)
    R = np.zeros(5)
    
    r = 0
    status = 0
    fig, axs= plt.subplots(2, 3, figsize = (16,8))
    f = fit_func_list[fit_function_type]

    # go over Ar 36 to 40
    for i in range(5):
        # first linear regression 
        # fit whole raw data (no outlier is removed)
        n=0
        t = v_t[i, :, 1]
        v = v_t[i, :, 0]
        popt, _ = curve_fit(f, t, v)
        T0[i] = f(0, *popt)
        T0_SIGMA[i] = (np.std(np.abs(v - f(t, *popt))))/(np.sqrt(num))  # std of the error
        
        axs[i//3, i%3].plot(t, v, marker = 'o', label = "raw data")
        axs[i//3, i%3].plot(t, f(t, *popt), linestyle = '--', label = "fitted line")
        R[i] = r2_score(v,f(t, *popt))
        axs[i//3, i%3].set(xlabel = "t (sec)", ylabel = "mV")
        error = T0_SIGMA[i]
        # second linear regression 
        # remove the manually selected outliers if necessary
        if  (R[i] <= 0.8):
            x = 0
            for j in range(num-1):
                r = v[j-x]-f(t[j-x], *popt)
                if r < 0 :
                    r = r *-1
                if r > error and x < 4:
                    x = x+1
                    mask[i, j] = 0
                    n=n+1
                if (mask[i, :] == 0).any():
                    selected_indices = np.where(mask[i, :] == 1)[0]
                    removed_indices = np.where(mask[i, :] == 0)[0]
                
                    t = v_t[i, selected_indices, 1]
                    v = v_t[i, selected_indices, 0]
                    
                    try:
                        popt, _ = curve_fit(f, t, v)
                        T0[i] = f(0, *popt)
                        T0_SIGMA[i] = (np.std(np.abs(v - f(t, *popt))))/(np.sqrt((num-n)))  # std of the error of second fit
                        R[i] = r2_score(v,f(t, *popt))
                    except:
                        status = 1
                    axs[i//3, i%3].plot(v_t[i, removed_indices, 1], v_t[i, removed_indices, 0], marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
                    axs[i//3, i%3].ticklabel_format(axis='y', style='sci', scilimits=(0,0))          
            axs[i//3, i%3].plot(t, f(t, *popt), linestyle = '--', label = "fitted line\n(exclude outliers)")
            
        axs[i//3, i%3].legend(bbox_to_anchor=(0.7,1.2), loc='upper left')
        axs[i//3, i%3].set_title("Ar {}\n{} = {} \nerror = {}\nR^2 = {}".format(i+36, r'$T_{0}$', '{:0.5e}'.format(T0[i]), '{:0.5e}'.format(T0_SIGMA[i]),'{:0.5e}'.format(R[i])), loc='left')
    
    axs[1,2].axis('off')
    plt.tight_layout()
    plt.savefig(".work/LR.png", dpi=200)
    plt.clf()
    plt.close("all")

    return [status, T0, T0_SIGMA, R],mask

def REcalculateT0(fit_function_type, v_t, mask,num):
    """
    Input:
    1. fit_function_type: 0 for linear, 1 for average

    2. v_t: raw voltage-time data

    3. mask: table of selected points

    Output:
    return [status, T0, T0_SIGMA, R^2]

    status: 
    0 success

    1 failed at fitting data from which the outliers are removed
    
    """

    # initialization
    T0 = np.zeros(5)
    T0_SIGMA = np.zeros(5)
    R = np.zeros(5)
    
    status = 0
    fig, axs = plt.subplots(2, 3, figsize = (16,8))
    f = fit_func_list[fit_function_type]

    # go over Ar 36 to 40
    for i in range(5):
        # first linear regression 
        # fit whole raw data (no outlier is removed)
        n=0
        t = v_t[i, :, 1]
        v = v_t[i, :, 0]
        popt, _ = curve_fit(f, t, v)
        T0[i] = f(0, *popt)
        for j in range(num):
            if mask[i,j]==0:
                n=n+1
        T0_SIGMA[i] = (np.std(np.abs(v - f(t, *popt))))/(np.sqrt((num-n)))  # std of the error
        
        axs[i//3, i%3].plot(t, v, marker = 'o', label = "raw data")
        axs[i//3, i%3].plot(t, f(t, *popt), linestyle = '--', label = "fitted line")
        R[i] = r2_score(v,f(t, *popt))
        axs[i//3, i%3].set(xlabel = "t (sec)", ylabel = "mV")

        # second linear regression 
        # remove the manually selected outliers if necessary
        if (mask[i, :] == 0).any():
            selected_indices = np.where(mask[i, :] == 1)[0]
            removed_indices = np.where(mask[i, :] == 0)[0]
            
            t = v_t[i, selected_indices, 1]
            v = v_t[i, selected_indices, 0]
            
            try:
                popt, _ = curve_fit(f, t, v)
                T0[i] = f(0, *popt)
                T0_SIGMA[i] = (np.std(np.abs(v - f(t, *popt))))/(np.sqrt((num-n))) # std of the error of second fit
                axs[i//3, i%3].plot(t, f(t, *popt), linestyle = '--', label = "fitted line\n(exclude outliers)")
                R[i] = r2_score(v,f(t, *popt))
            except:
                status = 1
                
            axs[i//3, i%3].plot(v_t[i, removed_indices, 1], v_t[i, removed_indices, 0], marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
            axs[i//3, i%3].ticklabel_format(axis='y', style='sci', scilimits=(0,0))
       
        axs[i//3, i%3].legend(bbox_to_anchor=(0.7,1.2), loc='upper left')
        axs[i//3, i%3].set_title("Ar {}\n{} = {} \nerror = {}\nR^2 = {}".format(i+36, r'$T_{0}$', '{:0.5e}'.format(T0[i]), '{:0.5e}'.format(T0_SIGMA[i]),'{:0.5e}'.format(R[i])), loc='left')
    
    axs[1,2].axis('off')
    plt.tight_layout()
    plt.savefig(".work/LR.png", dpi=200)
    plt.clf()
    plt.close("all")

    return [status, T0, T0_SIGMA, R]

def getDFStatistics_ls(file, mask,constants, Ncolor, Nmaker):
    fig, n = plt.subplots()
    with open(file, 'r') as f:
        data = f.readlines()
    # Normalize V2.0 (88-col K/Ca) → V3.7 (98-col Ca/K) in memory
    data = normalize_csv_to_v37(data)
    # Loose header check: 88 or 98 cols accepted
    _hdr_cols = data[0].rstrip().split(',') if data else []
    if len(_hdr_cols) not in (88, 98):
        raise Exception(f"Wrong data format! Expected 88 or 98 cols, got {len(_hdr_cols)}")
    
    i = 0
    while i != (len(data)-2):
        if data[i].split(',')[17] == "nan":
            data.pop(i)
            i=i-1
        i=i+1

    x = np.zeros(len(data)-2)  
    y = np.zeros(len(x)) 
    x_std = np.zeros(len(x)) 
    y_std = np.zeros(len(x)) 
    T_all = np.zeros(len(x)) 
    T_std_all = np.zeros(len(x)) 
    T_sum = 0 
    mswd = 0
    wma = 0
    
    for i in range (len(data)-2):
        x[i] = float(data[i+1].split(',')[46])/float(data[i+1].split(',')[7]) 
        y[i] = float(data[i+1].split(',')[61])/float(data[i+1].split(',')[7])
        x_std[i] = float(data[i+1].split(',')[47])/float(data[i+1].split(',')[8]) 
        y_std[i] = float(data[i+1].split(',')[62])/float(data[i+1].split(',')[8])
        T_all[i] = float(data[i+1].split(',')[17])
        T_std_all[i] = float(data[i+1].split(',')[18])
    j = 0
    for i in range (len(y)):
        if x[i-j] < 0 or y[i-j] < 0:
            x = np.delete(x,[i-j])
            y = np.delete(y,[i-j])
            x_std = np.delete(x_std,[i-j])
            y_std = np.delete(y_std,[i-j])
            T_all = np.delete(T_all,[i-j])
            T_std_all = np.delete(T_std_all,[i-j])
            j = j+1
            
    popt, _ = curve_fit(linear, x, y)
    n.plot(x,y,marker = Nmaker,linestyle = 'None', label = "data")
    n.plot(x, linear(x, *popt), linestyle = '--', label = "fitted line")
    n.set_xlabel('39^Ar/36^Ar')
    n.set_ylabel('40^Ar/36^Ar')
   
    if (mask[:] == 0).any():
        j = 0
        for i in range(len(y)):
            if(mask[i]==0):
                fx = x[i-j]
                fy = y[i-j]
                x = np.delete(x,[i-j])
                y = np.delete(y,[i-j])
                x_std = np.delete(x_std,[i-j])
                y_std = np.delete(y_std,[i-j])
                T_all = np.delete(T_all,[i-j])
                T_std_all = np.delete(T_std_all,[i-j])
                n.plot(fx, fy, marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
                j=j+1
    for i in range (len(y)): 
        t = np.linspace(0, 2*pi, 100)
        n.plot( x[i]+x_std[i]*np.cos(t) , y[i]+y_std[i]*np.sin(t),color='lightgray',linestyle='-')
    popt, _ = curve_fit(linear, x, y)
    n.plot(x, linear(x, *popt), linestyle = '--', label = "fitted line(exclude outliers)", color = Ncolor)
    
    popt, _ = curve_fit(linear, x, y)
    n.plot(0, linear(0, *popt), marker = Nmaker,linestyle = 'None', label = "fitted line(exclude outliers)", color = 'r')
    n = linear(0,*popt)
    popt, _ = curve_fit(linear, x_std, y_std)
    n_std = linear(0,*popt)    
    
    plt.savefig(".work/DFN.png", dpi = 200)
    
    fig, iv = plt.subplots()
    
    x = np.zeros(len(data)-2)  
    y = np.zeros(len(x)) 
    x_std = np.zeros(len(x)) 
    y_std = np.zeros(len(x)) 
    
    for i in range (len(data)-2):
        x[i] = float(data[i+1].split(',')[46])/float(data[i+1].split(',')[61]) 
        y[i] = float(data[i+1].split(',')[7])/float(data[i+1].split(',')[61])
        x_std[i] = float(data[i+1].split(',')[47])/float(data[i+1].split(',')[62]) 
        y_std[i] = float(data[i+1].split(',')[8])/float(data[i+1].split(',')[62])
     
    j = 0
    for i in range (len(y)):
        if x[i-j] < 0 or y[i-j] < 0:
            x = np.delete(x,[i-j])
            y = np.delete(y,[i-j])
            x_std = np.delete(x_std,[i-j])
            y_std = np.delete(y_std,[i-j])
            j = j+1
    
    popt, _ = curve_fit(linear, x, y)
    iv.plot(x,y,marker = Nmaker,linestyle = 'None', label = "data")
    iv.plot(x, linear(x, *popt), linestyle = '--', label = "fitted line")
    iv.set_xlabel('39^Ar/40^Ar')
    iv.set_ylabel('36^Ar/40^Ar')
   
    if (mask[:] == 0).any():
        j = 0
        for i in range(len(y)):
            if(mask[i]==0):
                fx = x[i-j]
                fy = y[i-j]
                x = np.delete(x,[i-j])
                y = np.delete(y,[i-j])
                x_std = np.delete(x_std,[i-j])
                y_std = np.delete(y_std,[i-j])
                iv.plot(fx, fy, marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
                j=j+1
    for i in range (len(y)): 
        t = np.linspace(0, 2*pi, 100)
        iv.plot( x[i]+x_std[i]*np.cos(t) , y[i]+y_std[i]*np.sin(t),color='lightgray',linestyle='-')
      
    iv.plot(x, linear(x, *popt), linestyle = '--', label = "fitted line(exclude outliers)",color = Ncolor)
    
    popt, _ = curve_fit(linear, x, y,)
    a = -popt[1]/popt[0]
    iv.plot(a,0,  marker = Nmaker,linestyle = 'None', label = "fitted line(exclude outliers)", color = 'r')
    iv = linear(0,*popt)
    popt, _ = curve_fit(linear, x_std, y_std)
    iv_std = linear(0,*popt)    
    
    plt.savefig(".work/DFI.png", dpi = 200)
    
    J = float(data[1].split(',')[4])
    J_std = float(data[1].split(',')[5])
    T = np.log(1 + J*iv) / float(constants[14]) #Lambda
    T_std = np.sqrt((J**2 * iv_std**2 + iv**2 * J_std**2)/ ((float(constants[14])*(1+iv*J))**2)) #Lambda
    
    for i in range(len(y)):
        T_sum = T_sum + T_all[i]
    T_sum = T_sum/len(y)

    for i in range(len(y)):
        mswd = (((T_sum-T_all[i])**2)/(T_std_all[i]**2))+mswd
    mswd = 1/(len(y)-1)*mswd

    for i in range(len(y)):
        wma = wma+((1/(T_std_all[i]**2)*T_all[i])/(1/(T_std_all[i]**2)))
    plt.clf()
    plt.close("all")

    return [n,n_std,iv,iv_std,mswd,wma,T,T_std]

def getDFStatistics_sh(file, mask, constants, Ncolor, Nmaker,
                       xlim=None, ylim=None, legend_name=None,
                       return_limits=False, show_temp=False,
                       show_atm=False, atm_ratio=298.56,
                       pname=None, style='pyADR',
                       iso_groups=None, group_colors=None,
                       return_points=False, show_legend=True,
                       show_group_fits=True, show_overall_fit=True):
    """
    Generate isochron diagrams for step heating data.
    
    Refactored version: preserves original architecture while integrating V2.5 bug fixes.
    
    Parameters:
    -----------
    file : str
        Path to data file
    mask : array-like
        Mask array for data selection (1=include, 0=exclude)
    constants : array-like
        Physical constants array
    Ncolor : str
        Color for fitted line (exclude outliers)
    Nmaker : str
        Marker style for data points
    xlim : tuple, optional
        X-axis limits (xmin, xmax)
    ylim : tuple, optional
        Y-axis limits (ymin, ymax)
    legend_name : str, optional
        Title for the plot
    return_limits : bool, optional
        If True, return axis limits
    show_temp : bool, optional
        If True, show temperature labels
    show_atm : bool, optional
        If True, show atmospheric value marker
    atm_value : float, optional
        Atmospheric 40Ar/36Ar value (default: 298.56)
    
    Returns:
    --------
    list : [n_intercept, n_std, iv_intercept, iv_std, mswd, wma, T, T_std]
    dict (optional) : {"DFN": (xlim, ylim), "DFI": (xlim, ylim)} if return_limits=True
    """
    
    # =========================================================
    # SETUP: Create output directory and initialize variables
    # =========================================================
    outdir = os.path.join(os.path.dirname(__file__), ".work")
    os.makedirs(outdir, exist_ok=True)
    
    # Set atmospheric value from parameter
    atm_value = atm_ratio
    
    # Initialize return values with safe defaults
    n = np.nan
    n_std = np.nan
    iv = np.nan
    iv_std = np.nan
    mswd = 0
    wma = 0
    T = np.nan
    T_std = np.nan
    
    # Initialize axis limits
    lim_DFN = ((0.0, 1.0), (0.0, 1.0))
    lim_DFI = ((0.0, 1.0), (0.0, 1.0))
    
    # =========================================================
    # READ DATA: Load file with proper encoding
    # =========================================================
    print(f"\n[DEBUG] Reading file: {file}")
    
    try:
        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
            data = f.readlines()
        # Normalize V2.0 (88-col K/Ca) → V3.7 (98-col Ca/K) in memory
        data = normalize_csv_to_v37(data)
        print(f"[DEBUG] Successfully read {len(data)} lines from file")
    except Exception as e:
        print(f"[ERROR] Cannot read file: {e}")
        raise Exception(f"Cannot read file: {e}")
    
    if len(data) < 2:
        print(f"[ERROR] File too short: only {len(data)} lines")
        raise Exception(f"File too short: only {len(data)} lines (need at least 2 lines)")
    
    # Check header - allow both old (88 cols) and new (98 cols) format
    print(f"[DEBUG] Checking header format...")
    
    # Base header (first 88 columns)
    base_header = "Samp#,Min,IRR,deg C,J,J_std,J_int,36Ar(a),36Ar(a)_std,37Ar(ca),37Ar(ca)_std,38Ar(cl),38Ar(cl)_std,39Ar(k),39Ar(k)_std,40Ar(r),40Ar(r)_std,Age(Ma),Age_std(Ma),40Ar(r)(%),39Ar(k)(%),40Ar(r)(%)(step heating),39Ar(k)(%)(step heating),Ca/K,Ca/K_std,Degassing Patterns,36Ar(a),36Ar(a)_std,36Ar(c),36Ar(c)_std,36Ar(ca),36Ar(ca)_std,36Ar(cl),36Ar(cl)_std,37Ar(ca),37Ar(ca)_std,38Ar(a),38Ar(a)_std,38Ar(c),38Ar(c)_std,38Ar(k),38Ar(k)_std,38Ar(ca),38Ar(ca)_std,38Ar(cl),38Ar(cl)_std,39Ar(k),39Ar(k)_std,39Ar(ca),39Ar(ca)_std,40Ar(r),40Ar(r)_std,40Ar(a),40Ar(a)_std,40Ar(c),40Ar(c)_std,40Ar(k),40Ar(k)_std,Additional Parameters,40(r)/39(k),40(r)/39(k)_std,40(r+a),40(r+a)_std,40Ar/39Ar,40Ar/39Ar_std,37Ar/39Ar,37Ar/39Ar_std,36Ar/39Ar,36Ar/39Ar_std,Parameters,39Ar/37Ar(ca),39Ar/37Ar(ca)_std,36Ar/37Ar(ca),36Ar/37Ar(ca)_std,40Ar/39Ar(k),40Ar/39Ar(k)_std,38Ar/39Ar(k),38Ar/39Ar(k)_std,39Ar/37Ar(k),39Ar/37Ar(k)_std,36Ar/38Ar(cl),36Ar/38Ar(cl)_std,40Ar/36Ar(a),40Ar/36Ar(a)_std,38Ar/36Ar(a),38Ar/36Ar(a)_std,Lambda,numCycle"
    
    # Extended header (98 columns) 
    extended_header = base_header + ",normal isochron,40Ar(m)/36Ar(m),40Ar(m)/36Ar(m)_std,39Ar(m)/36Ar(m),39Ar(m)/36Ar(m)_std,inverse isochron,36Ar(m)/40Ar(m),36Ar(m)/40Ar(m)_std,39Ar(m)/40Ar(m),39Ar(m)/40Ar(m)_std"
    
    actual_header = data[0].rstrip()
    actual_col_count = len(actual_header.split(','))
    
    # Accept both formats
    if actual_header == base_header:
        print(f"[DEBUG] Using OLD format (88 columns) - will calculate ratios")
    elif actual_header == extended_header:
        print(f"[DEBUG] Using NEW format (98 columns) - will read pre-calculated ratios")
    else:
        # Check if it's close enough (same number of columns)
        if actual_col_count == 88 or actual_col_count == 98:
            print(f"[WARNING] Header text doesn't match exactly but column count is correct ({actual_col_count})")
            print(f"[WARNING] Proceeding anyway...")
        else:
            print(f"[ERROR] Header format mismatch!")
            print(f"[ERROR] Expected 88 or 98 columns, got {actual_col_count}")
            print(f"[ERROR] First 100 chars of actual header:")
            print(f"        {actual_header[:100]}")
            raise Exception("Wrong data format!")
    
    print(f"[DEBUG] Header check passed ✓")
    
    # Remove rows with nan Age
    # FIX (off-by-one): strip trailing blank lines first so detection is robust,
    # then iterate over actual data rows (skip header at data[0]).
    # Old code: while i != (len(data) - 2): ...
    # That assumed exactly one trailing blank row and silently dropped the last
    # real data row when the CSV had no trailing blank.
    print(f"[DEBUG] Removing rows with nan Age...")
    while data and not data[-1].strip():
        data.pop()
    original_rows = len(data) - 1
    i = 1  # start from first data row, skip header
    while i < len(data):
        parts = data[i].split(',')
        if len(parts) > 17 and parts[17].strip() == "nan":
            print(f"[DEBUG] Removing row {i}: Age = nan")
            data.pop(i)
            # do not advance i; next row shifted into this slot
        else:
            i += 1
    
    nstep = len(data) - 1
    removed_rows = original_rows - nstep
    print(f"[DEBUG] Removed {removed_rows} rows with nan Age")
    print(f"[DEBUG] Valid data rows: {nstep}")
    
    if nstep < 2:
        print(f"[ERROR] Not enough valid data rows!")
        print(f"[ERROR] Need at least 2 rows, but only have {nstep}")
        raise Exception(f"Not enough steps to plot diagram. Need >=2, got {nstep}")
    
    # =========================================================
    # MASK HANDLING: Adjust mask size to match data
    # =========================================================
    mask = np.asarray(mask, dtype=float).copy()
    if mask.size != nstep:
        if mask.size < nstep:
            # Pad with 1s (include by default)
            mask = np.pad(mask, (0, nstep - mask.size), constant_values=1.0)
        else:
            # Truncate
            mask = mask[:nstep]
    
    # =========================================================
    # HELPER FUNCTION: Apply user-defined axis controls
    # =========================================================
    def apply_controls(ax, target=None):
        """FIX: apply limits only when target matches pname (or pname is None)."""
        apply_limits = (pname is None) or (target is None) or (pname == target)

        if apply_limits and xlim is not None:
            xmin, xmax = float(xlim[0]), float(xlim[1])
            print(f"[DEBUG] Setting X limits ({target}): {xmin} to {xmax}")
            if xmax - xmin > 1e6:
                print(f"[WARNING] X range too large, using auto")
                ax.autoscale(axis='x')
            elif xmax <= xmin:
                print(f"[WARNING] Invalid X range, using auto")
                ax.autoscale(axis='x')
            else:
                ax.set_xlim(xmin, xmax)

        if apply_limits and ylim is not None:
            ymin, ymax = float(ylim[0]), float(ylim[1])
            print(f"[DEBUG] Setting Y limits ({target}): {ymin} to {ymax}")
            if ymax - ymin > 1e6:
                print(f"[WARNING] Y range too large, using auto")
                ax.autoscale(axis='y')
            elif ymax <= ymin:
                print(f"[WARNING] Invalid Y range, using auto")
                ax.autoscale(axis='y')
            else:
                ax.set_ylim(ymin, ymax)

        if legend_name is not None:
            title_str = str(legend_name).strip()
            if title_str:
                ax.set_title(title_str)

        # Classic or pyADR frame / ticks
        _ist = _get_style(style)
        if _ist.get('classic'):
            ax.set_facecolor('white')
            ax.tick_params(which='both', direction='out',
                           top=True, right=True, bottom=True, left=True)
            ax.minorticks_on()
            for _sp in ax.spines.values():
                _sp.set_visible(True); _sp.set_linewidth(1.0); _sp.set_color('black')
        else:
            ax.set_facecolor('none')
            ax.tick_params(which='both', direction='out', top=False, right=False)

    def _iso_savefig(fig_obj, outpath):
        """Save isochron figure with correct facecolor."""
        _ist = _get_style(style)
        fig_obj.savefig(outpath, dpi=300,
                        facecolor='white' if _ist.get('classic') else 'none')

    # =========================================================
    # NORMAL ISOCHRON: X = 39Ar(m)/36Ar(m), Y = 40Ar(m)/36Ar(m)
    # Where (m) = measured = sum of all components
    # =========================================================
    fig_n, ax_n = plt.subplots(figsize=(8, 6), dpi=150)  # Fixed aspect ratio
    
    # Initialize data arrays
    x = np.zeros(nstep)  
    y = np.zeros(nstep) 
    x_std = np.zeros(nstep) 
    y_std = np.zeros(nstep) 
    T_all = np.zeros(nstep) 
    T_std_all = np.zeros(nstep) 
    
    # Extract data from file
    print(f"[DEBUG] Extracting data from {nstep} rows...")
    for i in range(nstep):
        parts = data[i + 1].split(',')
        
        if len(parts) < 80:
            print(f"[ERROR] Row {i+1} has only {len(parts)} columns (expected 80+)")
            raise Exception(f"Row {i+1}: Insufficient columns ({len(parts)} < 80)")
        
        # ========== READ ALL 36Ar COMPONENTS ==========
        # 36Ar(a) - column 26, 27
        try:
            Ar36_a = float(parts[26])
            Ar36_a_std = float(parts[27])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse 36Ar(a)")
            raise Exception(f"Row {i+1}: Invalid 36Ar(a) value")
        
        # 36Ar(c) - column 28, 29
        try:
            Ar36_c = float(parts[28])
            Ar36_c_std = float(parts[29])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse 36Ar(c)")
            raise Exception(f"Row {i+1}: Invalid 36Ar(c) value")
        
        # 36Ar(ca) - column 30, 31
        try:
            Ar36_ca = float(parts[30])
            Ar36_ca_std = float(parts[31])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse 36Ar(ca)")
            raise Exception(f"Row {i+1}: Invalid 36Ar(ca) value")
        
        # 36Ar(cl) - column 32, 33
        try:
            Ar36_cl = float(parts[32])
            Ar36_cl_std = float(parts[33])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse 36Ar(cl)")
            raise Exception(f"Row {i+1}: Invalid 36Ar(cl) value")
        
        # Calculate 36Ar(m) = sum of all 36Ar components
        Ar36_m = Ar36_a + Ar36_c + Ar36_ca + Ar36_cl
        Ar36_m_std = np.sqrt(Ar36_a_std**2 + Ar36_c_std**2 + Ar36_ca_std**2 + Ar36_cl_std**2)
        
        # ========== READ ALL 39Ar COMPONENTS ==========
        # 39Ar(k) - column 46, 47
        try:
            Ar39_k = float(parts[46])
            Ar39_k_std = float(parts[47])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse 39Ar(k)")
            raise Exception(f"Row {i+1}: Invalid 39Ar(k) value")
        
        # 39Ar(ca) - column 48, 49
        try:
            Ar39_ca = float(parts[48])
            Ar39_ca_std = float(parts[49])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse 39Ar(ca)")
            raise Exception(f"Row {i+1}: Invalid 39Ar(ca) value")
        
        # Calculate 39Ar(m) = sum of all 39Ar components
        Ar39_m = Ar39_k + Ar39_ca
        Ar39_m_std = np.sqrt(Ar39_k_std**2 + Ar39_ca_std**2)
        
        # ✅ BUG FIX: Calculate 40Ar(m) = 40Ar(r) + 40Ar(a) + 40Ar(c) + 40Ar(k)
        # Columns: 50-51 (r), 52-53 (a), 54-55 (c), 56-57 (k)
        try:
            Ar40_r = float(parts[50])
            Ar40_r_std = float(parts[51])
            Ar40_a = float(parts[52])
            Ar40_a_std = float(parts[53])
            Ar40_c = float(parts[54])
            Ar40_c_std = float(parts[55])
            Ar40_k = float(parts[56])
            Ar40_k_std = float(parts[57])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse 40Ar components")
            for col in [50, 51, 52, 53, 54, 55, 56, 57]:
                val = parts[col] if len(parts) > col else 'MISSING'
                print(f"        parts[{col}]={val}")
            raise Exception(f"Row {i+1}: Invalid 40Ar component values")
        
        Ar40_m = Ar40_r + Ar40_a + Ar40_c + Ar40_k
        Ar40_m_std = np.sqrt(Ar40_r_std**2 + Ar40_a_std**2 + Ar40_c_std**2 + Ar40_k_std**2)
        
        if i == 0:  # Print first row for debugging
            print(f"[DEBUG] First row values:")
            print(f"        36Ar(a) = {Ar36_a}")
            print(f"        39Ar(k) = {Ar39_k}")
            print(f"        40Ar(r) = {Ar40_r}")
            print(f"        40Ar(a) = {Ar40_a}")
            print(f"        40Ar(c) = {Ar40_c}")
            print(f"        40Ar(k) = {Ar40_k}")
            print(f"        40Ar(m) = {Ar40_m}")
            print(f"        36Ar(m) = {Ar36_m}")
            print(f"        39Ar(m) = {Ar39_m}")
        
        # Calculate ratios using measured totals
        # X = 39Ar(m) / 36Ar(m)
        # Y = 40Ar(m) / 36Ar(m)
        
        # Try to read from pre-calculated columns first (columns 89-92)
        # Column 88 is "normal isochron" separator
        if len(parts) > 92:
            try:
                y[i] = float(parts[89])      # 40Ar(m)/36Ar(m)
                y_std[i] = float(parts[90])  # std
                x[i] = float(parts[91])      # 39Ar(m)/36Ar(m)
                x_std[i] = float(parts[92])  # std
                
                if i == 0:
                    print(f"[DEBUG] Using pre-calculated Normal isochron ratios from CSV")
                    print(f"        Y (40Ar(m)/36Ar(m)) = {y[i]} ± {y_std[i]}")
                    print(f"        X (39Ar(m)/36Ar(m)) = {x[i]} ± {x_std[i]}")
            except (ValueError, IndexError):
                # Fall back to calculation
                x[i] = Ar39_m / Ar36_m if Ar36_m != 0 else np.nan
                y[i] = Ar40_m / Ar36_m if Ar36_m != 0 else np.nan
                
                if Ar36_m != 0 and Ar36_m_std != 0:
                    x_std[i] = x[i] * np.sqrt((Ar39_m_std/Ar39_m)**2 + (Ar36_m_std/Ar36_m)**2)
                    y_std[i] = y[i] * np.sqrt((Ar40_m_std/Ar40_m)**2 + (Ar36_m_std/Ar36_m)**2)
                else:
                    x_std[i] = np.nan
                    y_std[i] = np.nan
        else:
            # Old format CSV - calculate
            x[i] = Ar39_m / Ar36_m if Ar36_m != 0 else np.nan
            y[i] = Ar40_m / Ar36_m if Ar36_m != 0 else np.nan
            
            if Ar36_m != 0 and Ar36_m_std != 0:
                x_std[i] = x[i] * np.sqrt((Ar39_m_std/Ar39_m)**2 + (Ar36_m_std/Ar36_m)**2)
                y_std[i] = y[i] * np.sqrt((Ar40_m_std/Ar40_m)**2 + (Ar36_m_std/Ar36_m)**2)
            else:
                x_std[i] = np.nan
                y_std[i] = np.nan
        
        # Age data
        try:
            T_all[i] = float(parts[17])
            T_std_all[i] = float(parts[18])
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Row {i+1}: Cannot parse Age")
            raise Exception(f"Row {i+1}: Invalid Age value")
    
    print(f"[DEBUG] Data extraction complete")
    
    # ✅ BUG FIX: Use numpy boolean indexing instead of manual deletion
    valid = np.isfinite(x) & np.isfinite(y) & (x >= 0) & (y >= 0)
    original_indices = np.arange(nstep)[valid]  # Store original indices before filtering
    x = x[valid]
    y = y[valid]
    x_std = x_std[valid]
    y_std = y_std[valid]
    T_all = T_all[valid]
    T_std_all = T_std_all[valid]
    mask = mask[valid]
    
    # Check if we have enough data points
    if len(x) < 2:
        ax_n.set_xlabel('$^{39}$Ar/$^{36}$Ar')
        ax_n.set_ylabel('$^{40}$Ar/$^{36}$Ar')
        apply_controls(ax_n, target="DFN")
        lim_DFN = (ax_n.get_xlim(), ax_n.get_ylim())
        fig_n.savefig(os.path.join(outdir, "DFN.png"), dpi=300, facecolor=("white" if _get_style(style).get("classic") else "none"))
        plt.close('all')
        
        result = [n, n_std, iv, iv_std, mswd, wma, T, T_std]
        if return_limits:
            return result, {"DFN": lim_DFN, "DFI": lim_DFI, "DFN_pts": [], "DFI_pts": []}
        return result
    
    # First fit: all data
    try:
        popt, _ = curve_fit(linear, x, y)
        ax_n.plot(x, y, marker=Nmaker, linestyle='None', label="data")
        ax_n.plot(x, linear(x, *popt), linestyle='--', label="fitted line")
    except:
        ax_n.set_xlabel('$^{39}$Ar/$^{36}$Ar')
        ax_n.set_ylabel('$^{40}$Ar/$^{36}$Ar')
        apply_controls(ax_n, target="DFN")
        lim_DFN = (ax_n.get_xlim(), ax_n.get_ylim())
        fig_n.savefig(os.path.join(outdir, "DFN.png"), dpi=300, facecolor=("white" if _get_style(style).get("classic") else "none"))
        plt.close('all')
        
        result = [n, n_std, iv, iv_std, mswd, wma, T, T_std]
        if return_limits:
            return result, {"DFN": lim_DFN, "DFI": lim_DFI, "DFN_pts": [], "DFI_pts": []}
        return result
    
    ax_n.set_xlabel('$^{39}$Ar/$^{36}$Ar')
    ax_n.set_ylabel('$^{40}$Ar/$^{36}$Ar')
    
    # FIX#1: store all valid points for data-based axis range (before outlier deletion)
    x_all_pts = x.copy()
    y_all_pts = y.copy()

    # Remove outliers based on mask
    if (mask[:] == 0).any():
        j = 0
        for i in range(len(y)):
            if mask[i] == 0:
                fx = x[i - j]
                fy = y[i - j]
                x = np.delete(x, [i - j])
                y = np.delete(y, [i - j])
                x_std = np.delete(x_std, [i - j])
                y_std = np.delete(y_std, [i - j])
                T_all = np.delete(T_all, [i - j])
                T_std_all = np.delete(T_std_all, [i - j])
                original_indices = np.delete(original_indices, [i - j])  # FIX: keep in sync
                ax_n.plot(fx, fy, marker='x', markersize=12, linestyle='None', color='r')
                j = j + 1
    
    # Draw error ellipses
    for i in range(len(y)): 
        t = np.linspace(0, 2*pi, 100)
        ax_n.plot(x[i] + x_std[i]*np.cos(t), y[i] + y_std[i]*np.sin(t), 
                 color='lightgray', linestyle='-')
    
    # Second fit: exclude outliers (skip main line when group mode active)
    _has_groups = bool(iso_groups)
    try:
        popt, _ = curve_fit(linear, x, y)
        if show_overall_fit:
            ax_n.plot(x, linear(x, *popt), linestyle='--',
                     label="fitted line\n(exclude outliers)", color=Ncolor)
        # Calculate intercept
        ax_n.plot(0, linear(0, *popt), marker=Nmaker, linestyle='None', color='r')
        n = linear(0, *popt)
        # Calculate intercept uncertainty (from x_std, y_std fit)
        popt_std, _ = curve_fit(linear, x_std, y_std)
        n_std = linear(0, *popt_std)
    except:
        pass

    # FIX#8: Group regression lines for normal isochron
    if show_group_fits and _has_groups and group_colors:
        _grp_data_dfn = {}
        for _ai in range(len(x)):
            _oi = int(original_indices[_ai]) if _ai < len(original_indices) else _ai
            _gn = iso_groups.get(_oi)
            if _gn is not None:
                if _gn not in _grp_data_dfn:
                    _grp_data_dfn[_gn] = ([], [], [])
                _grp_data_dfn[_gn][0].append(x[_ai])
                _grp_data_dfn[_gn][1].append(y[_ai])
                _grp_data_dfn[_gn][2].append(y_std[_ai] if _ai < len(y_std) else float('nan'))
        _J_dfn, _Lam_dfn = np.nan, np.nan
        try:
            _J_dfn = float(data[1].split(',')[4])
            _Lam_dfn = float(data[1].split(',')[86])  # yr⁻¹ from CSV col 86
        except Exception:
            pass
        for _gn, (_gx, _gy, _gys) in sorted(_grp_data_dfn.items()):
            if len(_gx) < 1:
                continue
            _gxa, _gya, _gysa = np.array(_gx), np.array(_gy), np.array(_gys)
            _N_g = len(_gxa)
            _gc = group_colors[_gn - 1] if _gn - 1 < len(group_colors) else 'black'
            # highlight selected points
            ax_n.scatter(_gxa, _gya, color=_gc, zorder=8, s=60, edgecolors='black', linewidths=0.8)
            if len(_gx) == 1:
                # 1-point: anchor line through atmospheric intercept (0, atm_ratio)
                _atm_y_dfn = float(atm_ratio) if atm_ratio else 298.56
                _x0d, _y0d = float(_gxa[0]), float(_gya[0])
                if _x0d != 0:
                    _m1_dfn = (_y0d - _atm_y_dfn) / _x0d
                    _xint_dfn = -_atm_y_dfn / _m1_dfn if _m1_dfn != 0 else float('nan')
                    _xr = np.array([0.0, max(float(np.nanmax(_gxa))*1.1, abs(_xint_dfn)*0.1 if np.isfinite(_xint_dfn) else float(np.nanmax(_gxa))*1.1)])
                    ax_n.plot(_xr, _atm_y_dfn + _m1_dfn * _xr, '--', color=_gc, lw=1.5, zorder=5, label=f"G{_gn} (1pt)")
                    _age_str_1 = ""
                    if (np.isfinite(_xint_dfn) and _xint_dfn > 0
                            and np.isfinite(_J_dfn) and _J_dfn > 0
                            and np.isfinite(_Lam_dfn) and _Lam_dfn > 0):
                        _T_1 = np.log(1.0 + _J_dfn * _m1_dfn) / _Lam_dfn / 1e6
                        _age_str_1 = f"\nT={_T_1:.2f} Ma"
                    ax_n.annotate(
                        f"G{_gn}(1pt) N={_N_g}{_age_str_1}\n⁴⁰Ar/³⁶Ar={_atm_y_dfn:.0f}(fixed)",
                        xy=(_x0d, _y0d), fontsize=7, color=_gc, fontweight='bold',
                        ha='center', va='bottom',
                        bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.7, ec=_gc))
                continue
            try:
                _gopt, _ = curve_fit(linear, _gxa, _gya)
                _x_ext = np.array([0.0, float(np.max(_gxa)) * 1.1])
                ax_n.plot(_x_ext, linear(_x_ext, *_gopt), linestyle='-',
                         color=_gc, linewidth=2.0, zorder=5, label=f"Group {_gn}")
                _g_ic = linear(0.0, *_gopt)
                _age_str = ""
                if (np.isfinite(_J_dfn) and np.isfinite(_Lam_dfn)
                        and _Lam_dfn > 0 and _J_dfn > 0 and _gopt[0] > 0):
                    _T_g = np.log(1.0 + _J_dfn * _gopt[0]) / _Lam_dfn / 1e6
                    _age_str = f"\nT={_T_g:.1f} Ma"
                # MSWD: weighted by y_std (skip if errors invalid)
                _mswd_n = float('nan')
                if _N_g >= 3:
                    import numpy as _np_chk
                    _w = _gysa.astype(float)
                    if _np_chk.all(_np_chk.isfinite(_w)) and _np_chk.all(_w > 0):
                        _resid = _gya - linear(_gxa, *_gopt)
                        _mswd_n = float(_np_chk.sum((_resid / _w) ** 2) / (_N_g - 2))
                _mswd_str = f", MSWD={_mswd_n:.2f}" if _mswd_n == _mswd_n else ""
                # Stagger annotations vertically in axes-fraction to avoid overlap
                _ann_y_n = 0.98 - (_gn - 1) * 0.18
                ax_n.annotate(
                    f"G{_gn} N={_N_g}{_mswd_str}{_age_str}\n⁴⁰Ar/³⁶Ar={_g_ic:.0f}",
                    xy=(0.98, _ann_y_n), xycoords='axes fraction',
                    fontsize=7, color=_gc, fontweight='bold',
                    ha='right', va='top',
                    bbox=dict(boxstyle='round,pad=0.3', fc='gold', alpha=0.85, ec=_gc))
            except Exception:
                pass

    # FIX#2: Legend inside axes frame (no bbox_to_anchor)
    if show_legend:
        ax_n.legend(loc='upper left', fontsize=8, framealpha=0.85)

    # Show atmospheric value marker — top layer, no clipping
    if show_atm:
        ax_n.plot(0, atm_value, marker='o', markersize=9, color='red',
                 linestyle='None', zorder=100, markeredgewidth=1.5,
                 markerfacecolor='red', clip_on=False)

    # FIX#1: Auto axis from data points only (ignores error ellipse extents)
    if xlim is None and len(x_all_pts) > 0:
        _x0, _x1 = float(np.nanmin(x_all_pts)), float(np.nanmax(x_all_pts))
        _y0, _y1 = float(np.nanmin(y_all_pts)), float(np.nanmax(y_all_pts))
        _px = max(0.15 * (_x1 - _x0), abs(_x1) * 0.05, 0.5)
        _py = max(0.15 * (_y1 - _y0), abs(_y1) * 0.05, 1.0)
        ax_n.set_xlim(_x0 - _px, _x1 + _px)
        ax_n.set_ylim(max(0.0, _y0 - _py), _y1 + _py)

    apply_controls(ax_n, target="DFN")
    xlim_actual = ax_n.get_xlim()
    ylim_actual = ax_n.get_ylim()

    # FIX#4: Temperature labels with collision avoidance
    if show_temp:
        _xsc = max(xlim_actual[1] - xlim_actual[0], 1e-6)
        _ysc = max(ylim_actual[1] - ylim_actual[0], 1e-6)
        _placed = []
        for idx in range(len(x)):
            if np.isfinite(x[idx]) and np.isfinite(y[idx]) and idx < len(original_indices):
                original_idx = original_indices[idx]
                temp_str = data[original_idx + 1].split(",")[3]
                _tx, _ty = x[idx], y[idx]
                _va, _dy = 'bottom', 0.02 * _ysc
                for _att in range(4):
                    _ok = all(
                        abs(_tx - _px) / _xsc >= 0.05 or abs((_ty + _dy) - _py) / _ysc >= 0.04
                        for (_px, _py) in _placed
                    )
                    if _ok:
                        break
                    if _att == 0:
                        _dy = -0.02 * _ysc; _va = 'top'
                    elif _att == 1:
                        _dy = 0.04 * _ysc; _va = 'bottom'
                    elif _att == 2:
                        _dy = -0.04 * _ysc; _va = 'top'
                ax_n.text(_tx, _ty + _dy, f" {temp_str}°C",
                         fontsize=8, ha='left', va=_va, color='red')
                _placed.append((_tx, _ty + _dy))

    # Store DFN point data for group click detection
    _dfn_pts = [
        (float(x[i]), float(y[i]), int(original_indices[i]))
        for i in range(len(x))
        if i < len(original_indices) and np.isfinite(x[i]) and np.isfinite(y[i])
    ]

    # Axes bbox for coordinate mapping (saved without bbox_inches=tight → use get_position)
    _ax_pos_dfn = ax_n.get_position()
    _axes_bbox_dfn = (_ax_pos_dfn.x0, _ax_pos_dfn.y0, _ax_pos_dfn.x1, _ax_pos_dfn.y1)
    lim_DFN = (xlim_actual, ylim_actual)
    fig_n.savefig(os.path.join(outdir, "DFN.png"), dpi=300, facecolor=("white" if _get_style(style).get("classic") else "none"))  # Removed bbox_inches="tight"

    
    # =========================================================
    # INVERSE ISOCHRON: X = 39Ar(m)/40Ar(m), Y = 36Ar(m)/40Ar(m)
    # Where (m) = measured = sum of all components
    # =========================================================
    fig_iv, ax_iv = plt.subplots(figsize=(8, 6), dpi=150)  # Fixed aspect ratio
    
    # Re-initialize arrays (reload from original valid data)
    x_inv = np.zeros(nstep)  
    y_inv = np.zeros(nstep) 
    x_inv_std = np.zeros(nstep) 
    y_inv_std = np.zeros(nstep) 
    
    # Extract data again
    for i in range(nstep):
        parts = data[i + 1].split(',')
        
        # ========== READ ALL 36Ar COMPONENTS ==========
        Ar36_a = float(parts[26])
        Ar36_a_std = float(parts[27])
        Ar36_c = float(parts[28])
        Ar36_c_std = float(parts[29])
        Ar36_ca = float(parts[30])
        Ar36_ca_std = float(parts[31])
        Ar36_cl = float(parts[32])
        Ar36_cl_std = float(parts[33])
        
        # Calculate 36Ar(m)
        Ar36_m = Ar36_a + Ar36_c + Ar36_ca + Ar36_cl
        Ar36_m_std = np.sqrt(Ar36_a_std**2 + Ar36_c_std**2 + Ar36_ca_std**2 + Ar36_cl_std**2)
        
        # ========== READ ALL 39Ar COMPONENTS ==========
        Ar39_k = float(parts[46])
        Ar39_k_std = float(parts[47])
        Ar39_ca = float(parts[48])
        Ar39_ca_std = float(parts[49])
        
        # Calculate 39Ar(m)
        Ar39_m = Ar39_k + Ar39_ca
        Ar39_m_std = np.sqrt(Ar39_k_std**2 + Ar39_ca_std**2)
        
        # ✅ BUG FIX: Calculate 40Ar(m)
        Ar40_r = float(parts[50])
        Ar40_r_std = float(parts[51])
        Ar40_a = float(parts[52])
        Ar40_a_std = float(parts[53])
        Ar40_c = float(parts[54])
        Ar40_c_std = float(parts[55])
        Ar40_k = float(parts[56])
        Ar40_k_std = float(parts[57])
        
        Ar40_m = Ar40_r + Ar40_a + Ar40_c + Ar40_k
        Ar40_m_std = np.sqrt(Ar40_r_std**2 + Ar40_a_std**2 + Ar40_c_std**2 + Ar40_k_std**2)
        
        # Calculate inverse ratios using measured totals
        # X = 39Ar(m) / 40Ar(m)
        # Y = 36Ar(m) / 40Ar(m)
        
        # Try to read from pre-calculated columns first (columns 94-97)
        # Column 93 is "inverse isochron" separator
        if len(parts) > 97:
            try:
                y_inv[i] = float(parts[94])      # 36Ar(m)/40Ar(m)
                y_inv_std[i] = float(parts[95])  # std
                x_inv[i] = float(parts[96])      # 39Ar(m)/40Ar(m)
                x_inv_std[i] = float(parts[97])  # std
                
                if i == 0:
                    print(f"[DEBUG] Using pre-calculated Inverse isochron ratios from CSV")
                    print(f"        Y (36Ar(m)/40Ar(m)) = {y_inv[i]} ± {y_inv_std[i]}")
                    print(f"        X (39Ar(m)/40Ar(m)) = {x_inv[i]} ± {x_inv_std[i]}")
            except (ValueError, IndexError):
                # Fall back to calculation
                x_inv[i] = Ar39_m / Ar40_m if Ar40_m != 0 else np.nan
                y_inv[i] = Ar36_m / Ar40_m if Ar40_m != 0 else np.nan
                
                if Ar40_m != 0 and Ar40_m_std != 0:
                    x_inv_std[i] = x_inv[i] * np.sqrt((Ar39_m_std/Ar39_m)**2 + (Ar40_m_std/Ar40_m)**2)
                    y_inv_std[i] = y_inv[i] * np.sqrt((Ar36_m_std/Ar36_m)**2 + (Ar40_m_std/Ar40_m)**2)
                else:
                    x_inv_std[i] = np.nan
                    y_inv_std[i] = np.nan
        else:
            # Old format CSV - calculate
            x_inv[i] = Ar39_m / Ar40_m if Ar40_m != 0 else np.nan
            y_inv[i] = Ar36_m / Ar40_m if Ar40_m != 0 else np.nan
            
            if Ar40_m != 0 and Ar40_m_std != 0:
                x_inv_std[i] = x_inv[i] * np.sqrt((Ar39_m_std/Ar39_m)**2 + (Ar40_m_std/Ar40_m)**2)
                y_inv_std[i] = y_inv[i] * np.sqrt((Ar36_m_std/Ar36_m)**2 + (Ar40_m_std/Ar40_m)**2)
            else:
                x_inv_std[i] = np.nan
                y_inv_std[i] = np.nan
    
    # ✅ BUG FIX: Use boolean indexing and store original indices
    valid_inv = np.isfinite(x_inv) & np.isfinite(y_inv) & (x_inv >= 0) & (y_inv >= 0)
    original_indices_inv = np.arange(nstep)[valid_inv]  # Store original indices before filtering
    x_inv = x_inv[valid_inv]
    y_inv = y_inv[valid_inv]
    x_inv_std = x_inv_std[valid_inv]
    y_inv_std = y_inv_std[valid_inv]
    mask_inv = mask.copy()
    if len(mask_inv) == nstep:
        mask_inv = mask_inv[valid_inv]
    
    if len(x_inv) < 2:
        ax_iv.set_xlabel('$^{39}$Ar/$^{40}$Ar')
        ax_iv.set_ylabel('$^{36}$Ar/$^{40}$Ar')
        apply_controls(ax_iv, target="DFI")
        lim_DFI = (ax_iv.get_xlim(), ax_iv.get_ylim())
        fig_iv.savefig(os.path.join(outdir, "DFI.png"), dpi=300, facecolor=("white" if _get_style(style).get("classic") else "none"))
        plt.close('all')
        
        result = [n, n_std, iv, iv_std, mswd, wma, T, T_std]
        if return_limits:
            return result, {"DFN": lim_DFN, "DFI": lim_DFI, "DFN_pts": [], "DFI_pts": []}
        return result
    
    # First fit
    try:
        popt_inv, _ = curve_fit(linear, x_inv, y_inv)
        ax_iv.plot(x_inv, y_inv, marker=Nmaker, linestyle='None', label="data")
        if show_overall_fit:
            ax_iv.plot(x_inv, linear(x_inv, *popt_inv), linestyle='--', label="fitted line")
    except:
        ax_iv.set_xlabel('$^{39}$Ar/$^{40}$Ar')
        ax_iv.set_ylabel('$^{36}$Ar/$^{40}$Ar')
        apply_controls(ax_iv, target="DFI")
        lim_DFI = (ax_iv.get_xlim(), ax_iv.get_ylim())
        fig_iv.savefig(os.path.join(outdir, "DFI.png"), dpi=300, facecolor=("white" if _get_style(style).get("classic") else "none"))
        plt.close('all')
        
        result = [n, n_std, iv, iv_std, mswd, wma, T, T_std]
        if return_limits:
            return result, {"DFN": lim_DFN, "DFI": lim_DFI, "DFN_pts": [], "DFI_pts": []}
        return result
    
    ax_iv.set_xlabel('$^{39}$Ar/$^{40}$Ar')
    ax_iv.set_ylabel('$^{36}$Ar/$^{40}$Ar')
    
    # FIX#1: store all valid points for axis range (before outlier deletion)
    x_inv_all_pts = x_inv.copy()
    y_inv_all_pts = y_inv.copy()

    # Remove outliers
    if len(mask_inv) > 0 and (mask_inv[:] == 0).any():
        j = 0
        for i in range(len(y_inv)):
            if i < len(mask_inv) and mask_inv[i] == 0:
                fx = x_inv[i - j]
                fy = y_inv[i - j]
                x_inv = np.delete(x_inv, [i - j])
                y_inv = np.delete(y_inv, [i - j])
                x_inv_std = np.delete(x_inv_std, [i - j])
                y_inv_std = np.delete(y_inv_std, [i - j])
                original_indices_inv = np.delete(original_indices_inv, [i - j])  # FIX: keep in sync
                ax_iv.plot(fx, fy, marker='x', markersize=12, linestyle='None', color='r')
                j = j + 1
    
    # Draw error ellipses
    for i in range(len(y_inv)): 
        t = np.linspace(0, 2*pi, 100)
        ax_iv.plot(x_inv[i] + x_inv_std[i]*np.cos(t), 
                  y_inv[i] + y_inv_std[i]*np.sin(t),
                  color='lightgray', linestyle='-')
    
    # Second fit (skip main line when group mode active)
    inv_slope = np.nan
    inv_slope_std = np.nan
    try:
        popt_inv, pcov_inv = curve_fit(linear, x_inv, y_inv)
        if show_overall_fit:
            ax_iv.plot(x_inv, linear(x_inv, *popt_inv), linestyle='--',
                      label="fitted line (exclude outliers)", color=Ncolor)

        inv_slope = float(popt_inv[0])
        inv_intercept = float(popt_inv[1])

        # Calculate x-intercept
        a = -inv_intercept / inv_slope if inv_slope != 0 else 0
        ax_iv.plot(a, 0, marker=Nmaker, linestyle='None', color='r')

        iv = inv_intercept

        if pcov_inv is not None and pcov_inv.shape == (2, 2):
            inv_slope_std = float(np.sqrt(pcov_inv[0, 0])) if pcov_inv[0, 0] >= 0 else np.nan
            iv_std = float(np.sqrt(pcov_inv[1, 1])) if pcov_inv[1, 1] >= 0 else np.nan
    except Exception:
        pass

    # FIX#8: Group regression lines for inverse isochron
    if show_group_fits and _has_groups and group_colors:
        _grp_data_dfi = {}
        for _ai in range(len(x_inv)):
            _oi = int(original_indices_inv[_ai]) if _ai < len(original_indices_inv) else _ai
            _gn = iso_groups.get(_oi)
            if _gn is not None:
                if _gn not in _grp_data_dfi:
                    _grp_data_dfi[_gn] = ([], [], [])
                _grp_data_dfi[_gn][0].append(x_inv[_ai])
                _grp_data_dfi[_gn][1].append(y_inv[_ai])
                _grp_data_dfi[_gn][2].append(y_inv_std[_ai] if _ai < len(y_inv_std) else float('nan'))
        _J_dfi, _Lam_dfi = np.nan, np.nan
        try:
            _J_dfi = float(data[1].split(',')[4])
            _Lam_dfi = float(data[1].split(',')[86])  # yr⁻¹ from CSV col 86
        except Exception:
            pass
        for _gn, (_gx, _gy, _gys) in sorted(_grp_data_dfi.items()):
            if len(_gx) < 1:
                continue
            _gxa, _gya, _gysa = np.array(_gx), np.array(_gy), np.array(_gys)
            _N_gi = len(_gxa)
            _gc = group_colors[_gn - 1] if _gn - 1 < len(group_colors) else 'black'
            # highlight selected points
            ax_iv.scatter(_gxa, _gya, color=_gc, zorder=8, s=60, edgecolors='black', linewidths=0.8)
            if len(_gx) == 1:
                # 1-point: anchor line through atmospheric intercept (0, 1/atm_ratio)
                _atm_y_dfi = 1.0 / float(atm_ratio) if atm_ratio else 1.0/298.56
                _x0i, _y0i = float(_gxa[0]), float(_gya[0])
                if _x0i != 0:
                    _m1_dfi = (_y0i - _atm_y_dfi) / _x0i
                    _xint_dfi = -_atm_y_dfi / _m1_dfi if _m1_dfi != 0 else float('nan')
                    _xr_i = np.array([0.0, max(float(np.nanmax(_gxa))*1.1, abs(_xint_dfi)*0.1 if np.isfinite(_xint_dfi) else float(np.nanmax(_gxa))*1.1)])
                    ax_iv.plot(_xr_i, _atm_y_dfi + _m1_dfi * _xr_i, '--', color=_gc, lw=1.5, zorder=5, label=f"G{_gn} (1pt)")
                    _age_str_i1 = ""
                    _atm40_36 = 1.0 / _atm_y_dfi if _atm_y_dfi != 0 else float('nan')
                    if (np.isfinite(_xint_dfi) and _xint_dfi > 0
                            and np.isfinite(_J_dfi) and _J_dfi > 0
                            and np.isfinite(_Lam_dfi) and _Lam_dfi > 0):
                        _T_i1 = np.log(1.0 + _J_dfi / _xint_dfi) / _Lam_dfi / 1e6
                        _age_str_i1 = f"\nT={_T_i1:.2f} Ma"
                    ax_iv.annotate(
                        f"G{_gn}(1pt) N={_N_gi}{_age_str_i1}\n⁴⁰/³⁶={_atm40_36:.0f}(fixed)",
                        xy=(_x0i, _y0i), fontsize=7, color=_gc, fontweight='bold',
                        ha='center', va='bottom',
                        bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.7, ec=_gc))
                continue
            try:
                _gopt_i, _ = curve_fit(linear, _gxa, _gya)
                _x_ext = np.array([0.0, float(np.max(_gxa)) * 1.1])
                ax_iv.plot(_x_ext, linear(_x_ext, *_gopt_i), linestyle='-',
                          color=_gc, linewidth=2.0, zorder=5, label=f"Group {_gn}")
                _g_ic_inv = linear(0.0, *_gopt_i)
                _inv_sl = _gopt_i[0]
                # Age from X-intercept: 39/40 at y=0 → 40*/39 = -slope/ic
                _age_str_i = ""
                _atm_inv_str = f"{1.0/_g_ic_inv:.0f}" if _g_ic_inv != 0 else "—"
                if (np.isfinite(_J_dfi) and np.isfinite(_Lam_dfi)
                        and _Lam_dfi > 0 and _J_dfi > 0
                        and _inv_sl != 0 and _g_ic_inv != 0):
                    _F_xint = -_inv_sl / _g_ic_inv  # 40Ar*/39Ar from X-intercept
                    if _F_xint > 0:
                        _T_xint = np.log(1.0 + _J_dfi * _F_xint) / _Lam_dfi / 1e6
                        _age_str_i = f"\nT={_T_xint:.1f} Ma"
                # MSWD per group: weighted by y_inv_std (skip if errors invalid)
                _mswd_i = float('nan')
                if _N_gi >= 3:
                    import numpy as _np_chk
                    _wi = _gysa.astype(float)
                    if _np_chk.all(_np_chk.isfinite(_wi)) and _np_chk.all(_wi > 0):
                        _resid_i = _gya - linear(_gxa, *_gopt_i)
                        _mswd_i = float(_np_chk.sum((_resid_i / _wi) ** 2) / (_N_gi - 2))
                _mswd_str_i = f", MSWD={_mswd_i:.2f}" if _mswd_i == _mswd_i else ""
                # Mark group X-intercept (y=0) with colored circle — top layer
                _x_int_g = -_g_ic_inv / _inv_sl if _inv_sl != 0 else float('nan')
                if np.isfinite(_x_int_g) and _x_int_g > 0:
                    ax_iv.plot(_x_int_g, 0.0, marker='o', markersize=9,
                               color=_gc, linestyle='None',
                               zorder=100, clip_on=False,
                               markeredgecolor='black', markeredgewidth=0.8)
                # Stagger each group annotation vertically to avoid overlap
                _ann_y = 0.98 - (_gn - 1) * 0.18
                ax_iv.annotate(
                    f"G{_gn} N={_N_gi}{_mswd_str_i}{_age_str_i}\n⁴⁰/³⁶={_atm_inv_str}",
                    xy=(0.98, _ann_y), xycoords='axes fraction',
                    fontsize=7, color=_gc, fontweight='bold',
                    ha='right', va='top',
                    bbox=dict(boxstyle='round,pad=0.3', fc='gold', alpha=0.85, ec=_gc))
            except Exception:
                pass

    # FIX#2: Legend inside axes frame
    if show_legend:
        ax_iv.legend(loc='upper left', fontsize=8, framealpha=0.85)

    # Show atmospheric value marker (inverse) — top layer, no clipping
    if show_atm:
        inverse_atm = 1.0 / atm_value
        ax_iv.plot(0, inverse_atm, marker='o', markersize=9, color='red',
                  linestyle='None', zorder=100, markeredgewidth=1.5,
                  markerfacecolor='red', clip_on=False)

    # FIX#1: Auto axis from data points only
    if xlim is None and len(x_inv_all_pts) > 0:
        _x0i, _x1i = float(np.nanmin(x_inv_all_pts)), float(np.nanmax(x_inv_all_pts))
        _y0i, _y1i = float(np.nanmin(y_inv_all_pts)), float(np.nanmax(y_inv_all_pts))
        _pxi = max(0.15 * (_x1i - _x0i), abs(_x1i) * 0.05, 1e-5)
        _pyi = max(0.15 * (_y1i - _y0i), abs(_y1i) * 0.05, 1e-5)
        ax_iv.set_xlim(max(0.0, _x0i - _pxi), _x1i + _pxi)
        ax_iv.set_ylim(max(0.0, _y0i - _pyi), _y1i + _pyi)

    apply_controls(ax_iv, target="DFI")
    xlim_inv = ax_iv.get_xlim()
    ylim_inv = ax_iv.get_ylim()

    # FIX#4: Temperature labels with collision avoidance
    if show_temp:
        _xsc_i = max(xlim_inv[1] - xlim_inv[0], 1e-6)
        _ysc_i = max(ylim_inv[1] - ylim_inv[0], 1e-6)
        _placed_i = []
        for idx in range(len(x_inv)):
            if np.isfinite(x_inv[idx]) and np.isfinite(y_inv[idx]) and idx < len(original_indices_inv):
                original_idx = original_indices_inv[idx]
                temp_str = data[original_idx + 1].split(",")[3]
                _tx, _ty = x_inv[idx], y_inv[idx]
                _va, _dy = 'bottom', 0.02 * _ysc_i
                for _att in range(4):
                    _ok = all(
                        abs(_tx - _px) / _xsc_i >= 0.05 or abs((_ty + _dy) - _py) / _ysc_i >= 0.04
                        for (_px, _py) in _placed_i
                    )
                    if _ok:
                        break
                    if _att == 0:
                        _dy = -0.02 * _ysc_i; _va = 'top'
                    elif _att == 1:
                        _dy = 0.04 * _ysc_i; _va = 'bottom'
                    elif _att == 2:
                        _dy = -0.04 * _ysc_i; _va = 'top'
                ax_iv.text(_tx, _ty + _dy, f" {temp_str}°C",
                          fontsize=8, ha='left', va=_va, color='red')
                _placed_i.append((_tx, _ty + _dy))

    # Store DFI point data for group click detection
    _dfi_pts = [
        (float(x_inv[i]), float(y_inv[i]), int(original_indices_inv[i]))
        for i in range(len(x_inv))
        if i < len(original_indices_inv) and np.isfinite(x_inv[i]) and np.isfinite(y_inv[i])
    ]

    # Axes bbox for coordinate mapping
    _ax_pos_dfi = ax_iv.get_position()
    _axes_bbox_dfi = (_ax_pos_dfi.x0, _ax_pos_dfi.y0, _ax_pos_dfi.x1, _ax_pos_dfi.y1)
    lim_DFI = (xlim_inv, ylim_inv)
    fig_iv.savefig(os.path.join(outdir, "DFI.png"), dpi=300, facecolor=("white" if _get_style(style).get("classic") else "none"))  # Removed bbox_inches="tight"

    
    # =========================================================
    # CALCULATE AGE (Int age): from ISOCHRON SLOPE
    #
    # Normal isochron uses: 40/36 = (40/36)i + F*(39/36)  where F = (40* / 39*)
    # Inverse isochron uses: 36/40 = (36/40)i + (1/F)*(39/40)
    #
    # Here we calculate F from the inverse-isochron slope a:  a = 1/F  ->  F = 1/a
    # Then:  Age T = ln(1 + J*F) / Lambda
    # =========================================================
    try:
        J = float(data[1].split(',')[4])
        J_std = float(data[1].split(',')[5])
        Lambda = float(constants[14])

        if np.isfinite(inv_slope) and inv_slope != 0 and Lambda != 0:
            F = 1.0 / inv_slope
            # propagate slope uncertainty to F
            F_std = np.nan
            if np.isfinite(inv_slope_std):
                F_std = abs(inv_slope_std / (inv_slope**2))

            if np.isfinite(F):
                T = np.log(1.0 + J * F) / Lambda
                if np.isfinite(F_std):
                    T_std = np.sqrt((J**2 * F_std**2 + F**2 * J_std**2) /
                                    ((Lambda * (1.0 + F * J))**2))
    except Exception:
        pass
    
    # =========================================================
    # CALCULATE MSWD & WMA (ORIGINAL VERSION - PRESERVED)
    # =========================================================
    T_sum = 0 
    mswd = 0
    wma = 0
    
    # Calculate arithmetic mean (original method)
    for i in range(len(T_all)):
        T_sum = T_sum + T_all[i]
    if len(T_all) > 0:
        T_sum = T_sum / len(T_all)
    
    # Calculate MSWD (original formula)
    if len(T_all) > 1:
        for i in range(len(T_all)):
            mswd = (((T_sum - T_all[i])**2) / (T_std_all[i]**2)) + mswd
        mswd = 1 / (len(T_all) - 1) * mswd
    
    # Calculate WMA (original formula - simple weighted average)
    if len(T_all) > 0:
        for i in range(len(T_all)):
            if T_std_all[i] != 0:
                wma = wma + ((1 / (T_std_all[i]**2) * T_all[i]) / 
                            (1 / (T_std_all[i]**2)))
    
    plt.clf()
    plt.close("all")
    
    # =========================================================
    # RETURN RESULTS
    # =========================================================
    result = [n, n_std, iv, iv_std, mswd, wma, T, T_std]

    if return_limits:
        _limits = {"DFN": lim_DFN, "DFI": lim_DFI}
        if return_points:
            # FIX#8: include point data for click detection
            _limits["DFN_pts"] = _dfn_pts if '_dfn_pts' in dir() else []
            _limits["DFI_pts"] = _dfi_pts if '_dfi_pts' in dir() else []
        _limits["DFN_bbox"] = _axes_bbox_dfn if '_axes_bbox_dfn' in dir() else (0.125, 0.11, 0.9, 0.9)
        _limits["DFI_bbox"] = _axes_bbox_dfi if '_axes_bbox_dfi' in dir() else (0.125, 0.11, 0.9, 0.9)
        return result, _limits

    return result



def getSHStatistics(file, mask, constants, xlim=None, ylim=None, legend_name=None, show_legend=True,
                   log_y=False, show_group_span=False,
                    target_plot=None, style='pyADR',
                    step_groups=None, group_colors=None):
    if step_groups is None:
        step_groups = {}
    if group_colors is None:
        group_colors = ['#FF8C00','#1E90FF','#2ECC40','#FF4136','#B10DC9']
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    
    # Create figure with fixed aspect ratio (8:6) and high DPI
    fig, w = plt.subplots(figsize=(8, 6), dpi=150)
    
    # 讀取檔案，使用 utf-8 確保不會因為特殊符號報錯
    with open(file, 'r', encoding='utf-8-sig', errors='ignore') as f:
        data = f.readlines()
            
    # 核心修正：移除硬編碼 header 檢查，改用名稱索引 (解決 Ca/K 偏移問題)
    header = data[0].rstrip().split(',')
    col = {name.strip(): i for i, name in enumerate(header)}
    
    # 過濾 nan 的資料列，並建立數據列表
    data_rows = []
    for line in data[1:]:
        row = line.split(',')
        if len(row) > 17 and row[17].strip() != "nan":
            data_rows.append(row)

    n = len(data_rows)
    stepw = np.zeros(n)  # Step widths (not cumulative)
    y_age = np.zeros(n)
    y_err = np.zeros(n)
    sum39 = 0
    sum40 = 0
    
    for i in range(n):
        # Read step percentage (column 22) - already in percentage form
        stepw[i] = float(data_rows[i][22])
        
        # Read age (column 17) and error (column 18)
        y_age[i] = float(data_rows[i][17])
        y_err[i] = float(data_rows[i][18])
        
        # Accumulate gas amounts (for Total Age calculation)
        sum39 += float(data_rows[i][13])
        sum40 += float(data_rows[i][15])

    st = _get_style(style)
    # Per-axes facecolor (never touch rcParams to avoid global bleed)
    _bg = st.get('bg') or 'none'   # classic='white'; pyADR='none'(transparent)

    # Plot Age Spectrum step diagram
    j = 0  # Current X position
    step_data_dfw = []  # Store step info for mouse hover
    
    for i in range(n):
        width = stepw[i]  # Use step width directly
        x_start = j
        x_end = j + width
        
        # Store step info: (step_num, x_start, x_end, ar39_percent, age, age_std,
        #                   ar39_amount, temp_c, ar_r_pct, cak_step, cak_step_std)
        step_num = i + 1  # Step number (1-indexed)
        ar39_amount = float(data_rows[i][13])
        ar39_percent = width  # Width already represents the percentage
        temp_c = float(data_rows[i][3])  # deg C column

        # Per-step %40Ar* (radiogenic % of total 40Ar in this step)
        try:
            ar_r_pct = float(data_rows[i][col.get('40Ar(r)(%)', 19)])
        except (ValueError, IndexError, KeyError):
            ar_r_pct = float('nan')
        # Per-step Ca/K and uncertainty
        try:
            cak_step = float(data_rows[i][col.get('Ca/K', 23)])
        except (ValueError, IndexError, KeyError):
            cak_step = float('nan')
        try:
            cak_step_std = float(data_rows[i][col.get('Ca/K_std', 24)])
        except (ValueError, IndexError, KeyError):
            cak_step_std = float('nan')

        step_data_dfw.append((step_num, x_start, x_end, ar39_percent,
                             y_age[i], y_err[i], ar39_amount, temp_c,
                             ar_r_pct, cak_step, cak_step_std))
        
        # Bar fill: group color if grouped, else style default
        _fc_age = group_colors[step_groups[i]-1] if i in step_groups else st['age']
        square = patches.Rectangle((j, y_age[i]-y_err[i]), width, y_err[i]*2,
                                   edgecolor=st['edge'], facecolor=_fc_age,
                                   linewidth=st['lw'])
        w.add_patch(square)
        
        # Draw connecting line to next step
        if i < n - 1:
            # Line from right edge of current step to left edge of next step
            # At the height of current age
            x_current_right = j + width
            x_next_left = x_current_right  # Next step starts where current ends
            y_current = y_age[i]
            y_next = y_age[i + 1]
            
            # Draw line connecting steps (thinner)
            w.plot([x_current_right, x_next_left], [y_current, y_next], 
                   color='black', linewidth=0.5, linestyle='-')
        
        # If masked (excluded), mark with red X and remove from statistics
        if i < len(mask) and mask[i] == 0:
            w.plot(j + width/2, y_age[i], marker='x', markersize=12, color='r')
            sum39 -= float(data_rows[i][13])
            sum40 -= float(data_rows[i][15])
        j += width  # Accumulate position

    # 設定顯示範圍與標籤
    plt.xlim(0, 100)
    # Inward ticks on all 4 sides (NO.62 style)
    # ── Classic frame: outward ticks all 4 sides, closed box ─────────────
    if st.get('classic'):
        w.set_facecolor('white')
        w.tick_params(which='both', direction='out',
                         top=True, right=True, bottom=True, left=True)
        w.minorticks_on()
        for _sp in w.spines.values():
            _sp.set_visible(True); _sp.set_linewidth(1.0); _sp.set_color('black')
    else:
        w.set_facecolor('none')  # transparent → Qt widget bg shows through
        w.tick_params(which='both', direction='out',
                         top=False, right=False)
    
    # ── WMA overlay per group ──────────────────────────────────────────────
    if step_groups:
        # build cumulative x positions for each step
        cum_x = []
        _cx = 0.0
        for _sw in stepw:
            cum_x.append(_cx)
            _cx += _sw
        for grp in sorted(set(step_groups.values())):
            gi = [i for i, g in step_groups.items() if g == grp
                  and i < n and i < len(mask) and mask[i] == 1]
            if len(gi) < 1:
                continue
            _ages = y_age[gi]
            _errs = np.where(y_err[gi] > 0, y_err[gi], 1e-9)
            wt = 1.0 / _errs**2
            wma = float(np.sum(wt * _ages) / np.sum(wt))
            # y_err is already 2-sigma: wma_err computed this way IS 2-sigma → do NOT multiply by 2
            wma_err = float(1.0 / np.sqrt(np.sum(wt)))
            mswd = float(np.sum(wt * (_ages - wma)**2) / max(len(gi)-1, 1))
            gc = group_colors[grp-1] if grp-1 < len(group_colors) else 'gray'
            x0 = cum_x[min(gi)]
            x1 = cum_x[max(gi)] + stepw[max(gi)]
            ar39_pct = x1 - x0
            w.fill_between([x0, x1], [wma-wma_err]*2, [wma+wma_err]*2,
                           color=gc, alpha=0.25, zorder=3)
            w.plot([x0, x1], [wma, wma], color=gc, linewidth=1.5, zorder=4)
            w.text((x0+x1)/2, wma+wma_err*1.1,
                   f'WMA={wma:.1f}±{wma_err:.1f} Ma\nMSWD={mswd:.2f} n={len(gi)}\n³⁹Ar={ar39_pct:.1f}%',
                   ha='center', va='bottom', fontsize=7, color=gc, zorder=5)

    # Calculate Y-axis range using age ± std (robust to NaN)
    if n > 0:
        y_min = float(np.nanmin(y_age - y_err))
        y_max = float(np.nanmax(y_age + y_err))
        pad = 0.1 * (y_max - y_min) if y_max > y_min else 1.0  # 10% padding
        plt.ylim(y_min - pad, y_max + pad)
    
    # FIX: only apply limits when target is DFW
    if (target_plot is None or target_plot == 'DFW') and xlim is not None:
        plt.xlim(xlim[0], xlim[1])
    if (target_plot is None or target_plot == 'DFW') and ylim is not None:
        plt.ylim(ylim[0], ylim[1])
    w.set_xlabel('Cumulative $^{39}$Ar Released(%)')
    w.set_ylabel('Age (Ma)')
    if legend_name:
        plt.title(legend_name)
    # ── Group span indicator for DFW ────────────────────────────────────
    if show_group_span and step_groups:
        from collections import defaultdict
        _grp_steps = defaultdict(list)  # group_num → list of step indices (0-based)
        for _si, _gn in step_groups.items():
            if _si < n:
                _grp_steps[_gn].append(_si)
        _ylim_now = w.get_ylim()
        _y_span_base = _ylim_now[1] * 1.02
        for _gn, _gsteps in sorted(_grp_steps.items()):
            if len(_gsteps) < 1: continue
            _gsteps_sorted = sorted(_gsteps)
            # cumulative x positions
            _cum = [0.0]
            for _k in range(n): _cum.append(_cum[-1] + stepw[_k])
            _xs = _cum[_gsteps_sorted[0]]
            _xe = _cum[_gsteps_sorted[-1] + 1]
            _xmid = (_xs + _xe) / 2.0
            _gc = group_colors[_gn - 1] if group_colors and _gn-1 < len(group_colors) else 'black'
            # arrow <->
            w.annotate('', xy=(_xe, _y_span_base), xytext=(_xs, _y_span_base),
                       arrowprops=dict(arrowstyle='<->', color=_gc, lw=1.5))
            # WMA & MSWD
            _g_ages = np.array([y_age[_si] for _si in _gsteps_sorted])
            _g_errs = np.array([max(y_err[_si], 1e-6) for _si in _gsteps_sorted])
            _wts = 1.0 / _g_errs**2
            _wma = np.sum(_g_ages * _wts) / np.sum(_wts)
            _wma_err = 1.0 / np.sqrt(np.sum(_wts))
            _mswd = (np.sum((_g_ages - _wma)**2 / _g_errs**2) / max(len(_g_ages)-1, 1))
            _cum_ar = _xe - _xs
            _lbl = (f"G{_gn}: {_wma:.2f}±{_wma_err:.2f} Ma\n"
                    f"MSWD={_mswd:.2f}  ³⁹Ar={_cum_ar:.1f}%")
            _dy_txt = (_ylim_now[1] - _ylim_now[0]) * 0.04
            w.text(_xmid, _y_span_base + _dy_txt, _lbl,
                   ha='center', va='bottom', fontsize=7, color=_gc)
    # Axes bbox: use tight_layout + get_position (stable, DPI-independent, no bbox_inches='tight' shift)
    try:
        w.figure.tight_layout()
    except Exception:
        pass
    _ax_pos_dfw = w.get_position()
    _axes_bbox_dfw = (_ax_pos_dfw.x0, _ax_pos_dfw.y0, _ax_pos_dfw.x1, _ax_pos_dfw.y1)
    w.figure.savefig(".work/DFW.png", dpi=300,
                        facecolor='white' if st.get('classic') else 'none')
    _actual_xlim_dfw = tuple(float(v) for v in w.get_xlim())
    _actual_ylim_dfw = tuple(float(v) for v in w.get_ylim())

    # ========== Ca/K Spectrum (DFA) ==========
    fig_a, ax_a = plt.subplots(figsize=(8, 6), dpi=150)  # Fixed aspect ratio
    
    # Read Ca/K data (CSV already has Ca/K, not K/Ca!)
    y_cak = np.zeros(n)
    y_cak_err = np.zeros(n)
    
    # Try to find Ca/K column by name first
    if 'Ca/K' in col:
        cak_idx = col['Ca/K']
        cak_std_idx = col.get('Ca/K_std', cak_idx + 1)
        
        for i in range(n):
            try:
                y_cak[i] = float(data_rows[i][cak_idx])
                y_cak_err[i] = float(data_rows[i][cak_std_idx]) if cak_std_idx < len(data_rows[i]) else 0.0
            except (ValueError, IndexError):
                y_cak[i] = 0.0
                y_cak_err[i] = 0.0
    else:
        # Fallback: use fixed column indices (23 for Ca/K, 24 for Ca/K_std)
        for i in range(n):
            try:
                y_cak[i] = float(data_rows[i][23])
                y_cak_err[i] = float(data_rows[i][24]) if len(data_rows[i]) > 24 else 0.0
            except (ValueError, IndexError):
                y_cak[i] = 0.0
                y_cak_err[i] = 0.0
    
    # Plot Ca/K Spectrum step diagram
    j = 0
    step_data_dfa = []  # Store step info for mouse hover
    
    for i in range(n):
        width = stepw[i]  # Use step width directly
        x_start = j
        x_end = j + width
        
        # Store step info: (step_num, x_start, x_end, ar39_percent, cak, cak_std,
        #                   ar39_amount, ar_r_pct)
        step_num = i + 1  # Step number (1-indexed)
        ar39_amount = float(data_rows[i][13])
        ar39_percent = width  # Width already represents the percentage

        # Per-step %40Ar*
        try:
            ar_r_pct = float(data_rows[i][col.get('40Ar(r)(%)', 19)])
        except (ValueError, IndexError, KeyError):
            ar_r_pct = float('nan')

        step_data_dfa.append((step_num, x_start, x_end, ar39_percent,
                             y_cak[i], y_cak_err[i], ar39_amount,
                             ar_r_pct))
        
        _fc_cak = group_colors[step_groups[i]-1] if i in step_groups else st['cak']
        if st.get('classic'):
            square = patches.Rectangle((j, y_cak[i]-y_cak_err[i]), width, y_cak_err[i]*2,
                                       edgecolor='black', facecolor='white', linewidth=0.8)
        else:
            square = patches.Rectangle((j, y_cak[i]-y_cak_err[i]), width, y_cak_err[i]*2,
                                       edgecolor=st['edge'], facecolor=_fc_cak,
                                       linewidth=st['lw'])
        ax_a.add_patch(square)
        
        # Draw connecting line to next step
        if i < n - 1:
            # Line from right edge of current step to left edge of next step
            x_current_right = j + width
            x_next_left = x_current_right
            y_current = y_cak[i]
            y_next = y_cak[i + 1]
            
            # Draw line connecting steps (thinner)
            ax_a.plot([x_current_right, x_next_left], [y_current, y_next], 
                     color='black', linewidth=0.5, linestyle='-')
        
        if i < len(mask) and mask[i] == 0:
            ax_a.plot(j + width/2, y_cak[i], marker='x', markersize=12, color='r')
        j += width  # Accumulate position
    
    # (mean line removed per user request)
    
    # Set display range and labels
    plt.xlim(0, 100)
    
    # Calculate Y-axis range using Ca/K ± std (robust to NaN)
    if n > 0:
        y_min = float(np.nanmin(y_cak - y_cak_err))
        y_max = float(np.nanmax(y_cak + y_cak_err))
        pad = 0.1 * (y_max - y_min) if y_max > y_min else 1.0  # 10% padding
        plt.ylim(y_min - pad, y_max + pad)
    
    # FIX: only apply limits when target is DFA
    if (target_plot is None or target_plot == 'DFA') and xlim is not None:
        plt.xlim(xlim[0], xlim[1])
    if (target_plot is None or target_plot == 'DFA') and ylim is not None:
        plt.ylim(ylim[0], ylim[1])
    if log_y and (target_plot is None or target_plot == 'DFA'):
        _y0a, _y1a = ax_a.get_ylim()
        _eps = max(abs(_y1a)*1e-4, 1e-9)
        ax_a.set_ylim(max(_eps, _y0a), _y1a)
        ax_a.set_yscale('log')
    # ── Classic frame: outward ticks all 4 sides, closed box ─────────────
    if st.get('classic'):
        ax_a.set_facecolor('white')
        ax_a.tick_params(which='both', direction='out',
                         top=True, right=True, bottom=True, left=True)
        ax_a.minorticks_on()
        for _sp in ax_a.spines.values():
            _sp.set_visible(True); _sp.set_linewidth(1.0); _sp.set_color('black')
    else:
        ax_a.set_facecolor('none')  # transparent → Qt widget bg shows through
        ax_a.tick_params(which='both', direction='out',
                         top=False, right=False)
    ax_a.set_xlabel('Cumulative $^{39}$Ar Released(%)')
    ax_a.set_ylabel('Ca/K ratio')
    ax_a.text(0.01, 0.99,
              r'Ca/K $=\ \frac{^{37}\!\mathrm{Ar}_{Ca}}{^{39}\!\mathrm{Ar}_K}\ \times\ 0.55$',
              transform=ax_a.transAxes, ha='left', va='top',
              fontsize=8, color='#555555', style='italic')
    if legend_name:
        plt.title(legend_name)
    try:
        ax_a.figure.tight_layout()
    except Exception:
        pass
    _ax_pos_dfa = ax_a.get_position()
    _axes_bbox_dfa = (_ax_pos_dfa.x0, _ax_pos_dfa.y0, _ax_pos_dfa.x1, _ax_pos_dfa.y1)
    ax_a.figure.savefig(".work/DFA.png", dpi=300,
                          facecolor='white' if st.get('classic') else 'none')
    _actual_xlim_dfa = tuple(float(v) for v in ax_a.get_xlim())
    _actual_ylim_dfa = tuple(float(v) for v in ax_a.get_ylim())
    # ==========================================

    # ========== Cl/K Spectrum (DFC) ==========
    fig_cl, ax_cl = plt.subplots(figsize=(8, 6), dpi=150)

    y_clk = np.zeros(n)
    y_clk_err = np.zeros(n)

    ar38cl_idx    = col.get('38Ar(cl)')
    ar38cl_s_idx  = col.get('38Ar(cl)_std')
    ar39k_idx     = col.get('39Ar(k)')
    ar39k_s_idx   = col.get('39Ar(k)_std')
    CLK_FACTOR = 0.22  # Lo et al. (1994): Cl/K = (38Ar_Cl / 39Ar_K) × 0.22

    if ar38cl_idx is not None and ar39k_idx is not None:
        for i in range(n):
            try:
                ar38cl = float(data_rows[i][ar38cl_idx])
                ar38cl_s = float(data_rows[i][ar38cl_s_idx]) if ar38cl_s_idx is not None else 0.0
                ar39k  = float(data_rows[i][ar39k_idx])
                ar39k_s = float(data_rows[i][ar39k_s_idx]) if ar39k_s_idx is not None else 0.0
                if ar39k != 0:
                    y_clk[i] = CLK_FACTOR * ar38cl / ar39k
                    if ar38cl != 0:
                        y_clk_err[i] = abs(y_clk[i]) * np.sqrt(
                            (ar38cl_s / ar38cl) ** 2 + (ar39k_s / ar39k) ** 2)
            except (ValueError, IndexError, ZeroDivisionError):
                pass

    j = 0
    step_data_dfc = []
    for i in range(n):
        width = stepw[i]
        x_start = j
        x_end = j + width
        # Per-step %40Ar* and Ca/K for hover display
        try:
            _ar_r_pct = float(data_rows[i][col.get('40Ar(r)(%)', 19)])
        except (ValueError, IndexError, KeyError):
            _ar_r_pct = float('nan')
        try:
            _cak_step = float(data_rows[i][col.get('Ca/K', 23)])
        except (ValueError, IndexError, KeyError):
            _cak_step = float('nan')
        step_data_dfc.append((i + 1, x_start, x_end, width,
                              y_clk[i], y_clk_err[i], float(data_rows[i][13]),
                              _ar_r_pct, _cak_step))
        _fc_clk = group_colors[step_groups[i]-1] if i in step_groups else st['clk']
        if st.get('classic'):
            square = patches.Rectangle((j, y_clk[i] - y_clk_err[i]), width, y_clk_err[i] * 2,
                                       edgecolor='black', facecolor='white', linewidth=0.8)
        else:
            square = patches.Rectangle((j, y_clk[i] - y_clk_err[i]), width, y_clk_err[i] * 2,
                                       edgecolor=st['edge'], facecolor=_fc_clk,
                                       linewidth=st['lw'])
        ax_cl.add_patch(square)
        if i < n - 1:
            ax_cl.plot([j + width, j + width], [y_clk[i], y_clk[i + 1]],
                      color='black', linewidth=0.5, linestyle='-')
        if i < len(mask) and mask[i] == 0:
            ax_cl.plot(j + width / 2, y_clk[i], marker='x', markersize=12, color='r')
        j += width

    # (mean line removed per user request)

    plt.xlim(0, 100)
    if n > 0:
        y_min_cl = float(np.nanmin(y_clk - y_clk_err))
        y_max_cl = float(np.nanmax(y_clk + y_clk_err))
        pad_cl = 0.1 * (y_max_cl - y_min_cl) if y_max_cl > y_min_cl else 0.001
        plt.ylim(y_min_cl - pad_cl, y_max_cl + pad_cl)

    if (target_plot is None or target_plot == 'DFC') and xlim is not None:
        plt.xlim(xlim[0], xlim[1])
    if (target_plot is None or target_plot == 'DFC') and ylim is not None:
        plt.ylim(ylim[0], ylim[1])
    if log_y and (target_plot is None or target_plot == 'DFC'):
        _y0c, _y1c = ax_cl.get_ylim()
        _eps = max(abs(_y1c)*1e-4, 1e-9)
        ax_cl.set_ylim(max(_eps, _y0c), _y1c)
        ax_cl.set_yscale('log')
    # ── Classic frame: outward ticks all 4 sides, closed box ─────────────
    if st.get('classic'):
        ax_cl.set_facecolor('white')
        ax_cl.tick_params(which='both', direction='out',
                         top=True, right=True, bottom=True, left=True)
        ax_cl.minorticks_on()
        for _sp in ax_cl.spines.values():
            _sp.set_visible(True); _sp.set_linewidth(1.0); _sp.set_color('black')
    else:
        ax_cl.set_facecolor('none')  # transparent → Qt widget bg shows through
        ax_cl.tick_params(which='both', direction='out',
                         top=False, right=False)
    ax_cl.set_xlabel('Cumulative $^{39}$Ar Released(%)')
    ax_cl.set_ylabel('Cl/K ratio')
    ax_cl.text(0.01, 0.99,
               r'Cl/K $=\ \frac{^{38}\!\mathrm{Ar}_{Cl}}{^{39}\!\mathrm{Ar}_K}\ \times\ 0.22$',
               transform=ax_cl.transAxes, ha='left', va='top',
               fontsize=8, color='#555555', style='italic')
    if legend_name:
        plt.title(legend_name)
    try:
        ax_cl.figure.tight_layout()
    except Exception:
        pass
    _ax_pos_dfc = ax_cl.get_position()
    _axes_bbox_dfc = (_ax_pos_dfc.x0, _ax_pos_dfc.y0, _ax_pos_dfc.x1, _ax_pos_dfc.y1)
    ax_cl.figure.savefig(".work/DFC.png", dpi=300,
                           facecolor='white' if st.get('classic') else 'none')
    _actual_xlim_dfc = tuple(float(v) for v in ax_cl.get_xlim())
    _actual_ylim_dfc = tuple(float(v) for v in ax_cl.get_ylim())
    # ==========================================

    # 計算回傳值
    avg_age = np.mean([y_age[i] for i in range(n) if (i < len(mask) and mask[i] == 1)])
    F = sum40/sum39
    J_val = float(data_rows[0][4])
    T_total = np.log(1 + J_val * F) / float(constants[16]) / 1000000 # 轉為 Ma
    
    plt.close("all")
    
    # Return statistics, step data, and axes bboxes for mouse hover
    return {
        "statistics": [avg_age, T_total],
        "step_data": {
            "DFW": step_data_dfw,
            "DFA": step_data_dfa,
            "DFC": step_data_dfc
        },
        "axes_bbox": {
            "DFW": _axes_bbox_dfw,
            "DFA": _axes_bbox_dfa,
            "DFC": _axes_bbox_dfc,
        },
        "actual_xlim": {
            "DFW": _actual_xlim_dfw,
            "DFA": _actual_xlim_dfa,
            "DFC": _actual_xlim_dfc,
        },
        "actual_ylim": {
            "DFW": _actual_ylim_dfw,
            "DFA": _actual_ylim_dfa,
            "DFC": _actual_ylim_dfc,
        },
    }


def getDFStatistics_t(file, mask,power):
    fig, ax = plt.subplots()
    with open(file, 'r') as f:
        data = f.readlines()
    # Normalize V2.0 (88-col K/Ca) → V3.7 (98-col Ca/K) in memory
    data = normalize_csv_to_v37(data)
    # Loose header check: 88 or 98 cols accepted
    _hdr_cols = data[0].rstrip().split(',') if data else []
    if len(_hdr_cols) not in (88, 98):
        raise Exception(f"Wrong data format! Expected 88 or 98 cols, got {len(_hdr_cols)}")
    
    j = 0
    for i in range (len(data)-2):
        if float(data[i+1-j].split(',')[46])/float(data[i+1-j].split(',')[7]) < 0 or float(data[i+1-j].split(',')[61])/float(data[i+1-j].split(',')[7]) < 0 :
            data.pop(i-j)
            j=j+1  
        if data[i+1-j].split(',')[17] == "nan":
            data.pop(i-j)
            j=j+1

    x = np.zeros(len(data)-2)
    
    for i in range (len(data)-2):
        x[i] = float(data[i+1].split(',')[17])/pow(10,int(power))
   
    if (mask[:] == 0).any():
        j = 0
        for i in range(len(x)):
            if(mask[i]==0):
                x = np.delete(x,[i-j])
                j=j+1
    
    for i in range(len(x)):
        for j in range(len(x)-i-1):
            if x[j] > x[j+1]:
                temp = x[j]
                x[j] = x[j+1]
                x[j+1] = temp
    
    fig, ax = plt.subplots()
    bins = np.arange(-5, x[len(x)-1]+5)
    
    for count, edge in zip(*np.histogram(x, bins)):
        for i in range(count):
            ax.add_patch(plt.Rectangle((edge, i), 1, 1,
                                       alpha=0.5))
    
    x_d = np.linspace(-x[0]-5, x[len(x)-1]+5, 2000)
        
    density = sum(norm(xi).pdf(x_d) for xi in x)

    plt.fill_between(x_d, density, alpha=0.5, color = 'r')
    plt.plot(x, np.full_like(x, -0.1), '|k', markeredgewidth=1)
    
    plt.axis([x[0]-5, x[len(x)-1]+5, -0.2, len(x)])

    ax.set_xlabel('Age(10^'+str(power)+')')
    
    plt.savefig(".work/DFK.png", dpi = 200)
    plt.clf()
    plt.close("all")
    
    return 0

def getAirRatioStatistics(filelist):
    '''
    background1: published Ar 40/36 air background
    background2: published Ar 38/36 air background
    '''
    ratios = np.zeros((len(filelist), 2)) # [ratio pair, ratio value]

    for i, filename in enumerate(filelist):
        with open(filename, 'r') as f:
            data = f.readlines()

        # check header here
        if data[0].rstrip() != "Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma":
            raise Exception("Wrong data format!")

        ratios[i, 0] = float(data[4].split(',')[9])
        ratios[i, 1] = float(data[5].split(',')[9])
        
    for i in range(len(ratios)):
        if abs(ratios[i,0]) > 313 :
            ratios = np.delete(ratios,i,0)

    n = len(ratios)

    # calculate statistics
    statistics = np.zeros((2, 2)) # [ratio pair, mean/std]
    for i in range(2):
        statistics[i, 0] = np.mean(ratios[:, i])
        statistics[i, 1] = np.std(ratios[:, i])

    # plot air ratio distribution
    fig, axs = plt.subplots(1, 2, figsize = (6,4))
    ratio_pair = ["Ar 40/36", "Ar 38/36"]
    for i in range(2):
        axs[i].plot(np.zeros(len(filelist)), ratios[:, i], marker = 'x', markersize = 10, linestyle = 'None')
        axs[i].errorbar(0, statistics[i, 0], yerr = statistics[i, 1], color = 'k', capthick = 2, capsize = 3, marker = '_', markersize = 15)
        axs[i].set_aspect(7/axs[i].get_data_ratio())
        axs[i].axes.get_xaxis().set_visible(False)  # remove the x-axis and its ticks
        axs[i].set_title(ratio_pair[i])

    #plt.show()
    plt.savefig(".work/ARS.png", dpi = 200)

    return statistics,n

def getJStatistics(file, mask):
    plt.figure().clear()
    result = np.zeros(len(file))
    std = np.zeros(len(file))
    fx = np.zeros(len(file))
    avg_y = np.zeros(len(file))
    stdp = np.zeros(len(file))
    stdn = np.zeros(len(file))
    mean_y = np.zeros(len(file))
    meanp = np.zeros(len(file))
    meann = np.zeros(len(file))
    avg = 0.0
    mean = 0.0
    mean_std = 0.0
    
    for i, filename in enumerate(file):
        with open(filename, 'r') as f:
            data = f.readlines()
            
        # check header here
        if data[0].rstrip() != "file name,36Ar(a)[V],37Ar(ca)[V],39Ar(k)[V],40Ar(r)[V],40Ar(r)(%),39Ar(k)(%),Ca/K,Ca/K Sigma,J value,J Sigma,J Sigma int":
            raise Exception("Wrong data format!")

      
        result[i] = float(data[1].split(',')[9])
        std[i] = float(data[1].split(',')[10])
        mean = mean + (1/(std[i]**2)*result[i])
        mean_std = mean_std + 1/(std[i]**2)
        avg = avg + float(data[1].split(',')[9])
        fx[i] = i+1
    y = result
    y_std = std
    x = fx
    avg = avg/len(file)
    mean = mean/mean_std
    mean_std = np.sqrt(1/mean_std)
    y_stdp = (np.std(y)/len(y)**0.5) + avg
    y_stdn = avg - (np.std(y)/len(y)**0.5)
    
    for i in range (len(y)):
        if y[i] < y_stdn:
            mask[i] = 0
        if y[i] > y_stdp:
            mask[i] = 0
        
    for i in range (len(y)):
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
    for i, filename in enumerate(file):
        avg_y[i] = avg
    plt.plot(x,y,marker = 'o', label = "J data")
    plt.plot(x,avg_y,linestyle = '-', label = "average") 
    plt.plot(x,stdp,linestyle = '--', label = "std+") 
    plt.plot(x,stdn,linestyle = '--', label = "std-") 
        
           
    if (mask[:] == 0).any():
        avg = 0.0
        j = 0
        for i, filename in enumerate(file):
            if(mask[i]==0 and len(y)>1):
                x = np.delete(x,[i-j])
                np.where(x<i,x,x-1)
                y = np.delete(y,[i-j])
                y_std = np.delete(y_std,[i-j])
                plt.plot(fx[i], result[i], marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
                j=j+1
        avg_y = np.zeros(len(y))
        for i in range (len(y)): 
            avg = avg+y[i]
            mean = mean + (1/(y_std[i]**2)*y[i])
            mean_std = mean_std + 1/(y_std[i]**2)
        avg = avg/len(y) 
        mean = mean/mean_std
        mean_std = np.sqrt(1/mean_std)
        y_stdp = np.std(y) + avg
        y_stdn = avg-np.std(y)
        stdp = np.zeros(len(y))
        stdn = np.zeros(len(y))
        for i in range (len(y)):
            avg_y[i] = avg
            mean_y[i] = mean
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
            
           
        plt.plot(x, avg_y, linestyle = '-', label = "average\n(exclude outliers)")
        plt.plot(x,stdp,linestyle = '--', label = "std+") 
        plt.plot(x,stdn,linestyle = '--', label = "std-") 
           
    #plt.show()
    plt.savefig(".work/J.png", dpi = 200)
    plt.clf()
    plt.close("all")

    return [avg,(y_stdp-avg),mean,mean_std],mask

def getSaltStatistics(file, mask,salt):
    plt.figure().clear()
    result = np.zeros(len(file))
    std = np.zeros(len(file))
    fx = np.zeros(len(file))
    avg_y = np.zeros(len(file))
    stdp = np.zeros(len(file))
    stdn = np.zeros(len(file))
    mean_y = np.zeros(len(file))
    meanp = np.zeros(len(file))
    meann = np.zeros(len(file))
    avg = 0.0
    mean = 0.0
    mean_std = 0.0
    
    
    for i, filename in enumerate(file):
        with open(filename, 'r') as f:
            data = f.readlines()
            
        # check header here
        if data[0].rstrip() != "Samp#,,Ratio,Sigma":
            raise Exception("Wrong data format!")

        if(salt==39 or salt == 38):
            result[i] = float(data[2].split(',')[2])
            avg = avg + float(data[2].split(',')[2])
            std[i] = float(data[2].split(',')[3])
            mean = mean + (1/(std[i]**2)*result[i])
            mean_std = mean_std + 1/(std[i]**2)
            fx[i] = i+1
        elif(salt==37):
            result[i] = float(data[3].split(',')[2])
            avg = avg + float(data[3].split(',')[2])
            std[i] = float(data[3].split(',')[3])
            mean = mean + (1/(std[i]**2)*result[i])
            mean_std = mean_std + 1/(std[i]**2)
            fx[i] = i+1
        else:
            result[i] = float(data[1].split(',')[2])
            avg = avg + float(data[1].split(',')[2])
            std[i] = float(data[1].split(',')[3])
            mean = mean + (1/(std[i]**2)*result[i])
            mean_std = mean_std + 1/(std[i]**2)
            fx[i] = i+1
            
    y = result
    y_std = std
    x = fx
    avg = avg/len(file)
    mean = mean/mean_std
    mean_std = np.sqrt(1/mean_std)
    y_stdp = (np.std(y)/len(y)**0.5) + avg
    y_stdn = avg - (np.std(y)/len(y)**0.5)
    
    for i in range (len(y)):
        if y[i] < y_stdn:
            mask[i] = 0
        if y[i] > y_stdp:
            mask[i] = 0
        
    for i in range (len(y)):
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
    for i, filename in enumerate(file):
        avg_y[i] = avg
    plt.plot(x,y,marker = 'o', label = "J data")
    plt.plot(x,avg_y,linestyle = '-', label = "average") 
    plt.plot(x,stdp,linestyle = '--', label = "std+") 
    plt.plot(x,stdn,linestyle = '--', label = "std-") 
        
           
    if (mask[:] == 0).any():
        avg = 0.0
        j = 0
        for i, filename in enumerate(file):
            if(mask[i]==0 and len(y)>1):
                x = np.delete(x,[i-j])
                np.where(x<i,x,x-1)
                y = np.delete(y,[i-j])
                y_std = np.delete(y_std,[i-j])
                plt.plot(fx[i], result[i], marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
                j=j+1
        avg_y = np.zeros(len(y))
        for i in range (len(y)): 
            avg = avg+y[i]
            mean = mean + (1/(y_std[i]**2)*y[i])
            mean_std = mean_std + 1/(y_std[i]**2)
        avg = avg/len(y) 
        mean = mean/mean_std
        mean_std = np.sqrt(1/mean_std)
        y_stdp = np.std(y) + avg
        y_stdn = avg-np.std(y)
        stdp = np.zeros(len(y))
        stdn = np.zeros(len(y))
        for i in range (len(y)):
            avg_y[i] = avg
            mean_y[i] = mean
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
            
           
        plt.plot(x, avg_y, linestyle = '-', label = "average\n(exclude outliers)")
        plt.plot(x,stdp,linestyle = '--', label = "std+") 
        plt.plot(x,stdn,linestyle = '--', label = "std-") 
           
    #plt.show()
    plt.savefig(".work/Salt.png", dpi = 200)
    plt.clf()
    plt.close("all")

    return [avg,(y_stdp-avg),mean,mean_std],mask

def REgetSaltStatistics(file, mask,salt):
    plt.figure().clear()
    result = np.zeros(len(file))
    std = np.zeros(len(file))
    fx = np.zeros(len(file))
    avg_y = np.zeros(len(file))
    stdp = np.zeros(len(file))
    stdn = np.zeros(len(file))
    mean_y = np.zeros(len(file))
    meanp = np.zeros(len(file))
    meann = np.zeros(len(file))
    avg = 0.0
    mean = 0.0
    mean_std = 0.0
    
    
    for i, filename in enumerate(file):
        with open(filename, 'r') as f:
            data = f.readlines()
            
        # check header here
        if data[0].rstrip() != "Samp#,,Ratio,Sigma":
            raise Exception("Wrong data format!")

        if(salt==39 or salt == 38):
            result[i] = float(data[2].split(',')[2])
            avg = avg + float(data[2].split(',')[2])
            std[i] = float(data[2].split(',')[3])
            mean = mean + (1/(std[i]**2)*result[i])
            mean_std = mean_std + 1/(std[i]**2)
            fx[i] = i+1
        else:
            result[i] = float(data[1].split(',')[2])
            avg = avg + float(data[1].split(',')[2])
            std[i] = float(data[1].split(',')[3])
            mean = mean + (1/(std[i]**2)*result[i])
            mean_std = mean_std + 1/(std[i]**2)
            fx[i] = i+1
            
    y = result
    y_std = std
    x = fx
    avg = avg/len(file)
    mean = mean/mean_std
    mean_std = np.sqrt(1/mean_std)
    y_stdp = (np.std(y)/len(y)**0.5) + avg
    y_stdn = avg - (np.std(y)/len(y)**0.5)
        
    for i in range (len(y)):
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
            
    for i, filename in enumerate(file):
        avg_y[i] = avg
    plt.plot(x,y,marker = 'o', label = "J data")
    plt.plot(x,avg_y,linestyle = '-', label = "average") 
    plt.plot(x,stdp,linestyle = '--', label = "std+") 
    plt.plot(x,stdn,linestyle = '--', label = "std-") 
        
           
    if (mask[:] == 0).any():
        avg = 0.0
        j = 0
        for i, filename in enumerate(file):
            if(mask[i]==0):
                x = np.delete(x,[i-j])
                np.where(x<i,x,x-1)
                y = np.delete(y,[i-j])
                y_std = np.delete(y_std,[i-j])
                plt.plot(fx[i], result[i], marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
                j=j+1
        avg_y = np.zeros(len(y))
        for i in range (len(y)): 
            avg = avg+y[i]
            mean = mean + (1/(y_std[i]**2)*y[i])
            mean_std = mean_std + 1/(y_std[i]**2)
        avg = avg/len(y) 
        mean = mean/mean_std
        mean_std = np.sqrt(1/mean_std)
        y_stdp = np.std(y) + avg
        y_stdn = avg-np.std(y)
        stdp = np.zeros(len(y))
        stdn = np.zeros(len(y))
        for i in range (len(y)):
            avg_y[i] = avg
            mean_y[i] = mean
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
            
           
        plt.plot(x, avg_y, linestyle = '-', label = "average\n(exclude outliers)")
        plt.plot(x,stdp,linestyle = '--', label = "std+") 
        plt.plot(x,stdn,linestyle = '--', label = "std-") 
           
    #plt.show()
    plt.savefig(".work/Salt.png", dpi = 200)
    plt.clf()
    plt.close("all")
    

    return [avg,(y_stdp-avg),mean,mean_std]

def REgetJStatistics(file, mask):
    plt.figure().clear()
    result = np.zeros(len(file))
    std = np.zeros(len(file))
    fx = np.zeros(len(file))
    avg_y = np.zeros(len(file))
    stdp = np.zeros(len(file))
    stdn = np.zeros(len(file))
    mean_y = np.zeros(len(file))
    meanp = np.zeros(len(file))
    meann = np.zeros(len(file))
    avg = 0.0
    mean = 0.0
    mean_std = 0.0
    
    for i, filename in enumerate(file):
        with open(filename, 'r') as f:
            data = f.readlines()
            
        # check header here
        if data[0].rstrip() != "file name,36Ar(a)[V],37Ar(ca)[V],39Ar(k)[V],40Ar(r)[V],40Ar(r)(%),39Ar(k)(%),Ca/K,Ca/K Sigma,J value,J Sigma,J Sigma int":
            raise Exception("Wrong data format!")

      
        result[i] = float(data[1].split(',')[9])
        std[i] = float(data[1].split(',')[10])
        mean = mean + (1/(std[i]**2)*result[i])
        mean_std = mean_std + 1/(std[i]**2)
        avg = avg + float(data[1].split(',')[9])
        fx[i] = i+1
    y = result
    y_std = std
    x = fx
    avg = avg/len(file)
    mean = mean/mean_std
    mean_std = np.sqrt(1/mean_std)
    y_stdp = (np.std(y)/len(y)**0.5) + avg
    y_stdn = avg - (np.std(y)/len(y)**0.5)
    for i in range (len(y)):
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
    for i, filename in enumerate(file):
        avg_y[i] = avg
    plt.plot(x,y,marker = 'o', label = "J data")
    plt.plot(x,avg_y,linestyle = '-', label = "average") 
    plt.plot(x,stdp,linestyle = '--', label = "std+") 
    plt.plot(x,stdn,linestyle = '--', label = "std-") 
        
           
    if (mask[:] == 0).any():
        avg = 0.0
        j = 0
        for i, filename in enumerate(file):
            if(mask[i]==0):
                x = np.delete(x,[i-j])
                np.where(x<i,x,x-1)
                y = np.delete(y,[i-j])
                y_std = np.delete(y_std,[i-j])
                plt.plot(fx[i], result[i], marker = 'x', markersize = 12, linestyle = 'None', color = 'r')
                j=j+1
        avg_y = np.zeros(len(y))
        for i in range (len(y)): 
            avg = avg+y[i]
            mean = mean + (1/(y_std[i]**2)*y[i])
            mean_std = mean_std + 1/(y_std[i]**2)
        avg = avg/len(y) 
        mean = mean/mean_std
        mean_std = np.sqrt(1/mean_std)
        y_stdp = np.std(y) + avg
        y_stdn = avg-np.std(y)
        stdp = np.zeros(len(y))
        stdn = np.zeros(len(y))
        for i in range (len(y)):
            avg_y[i] = avg
            mean_y[i] = mean
            stdp[i] = y_stdp
            stdn[i] = y_stdn
            meanp[i] = mean_std + avg
            meann[i] = avg - mean_std
            
           
        plt.plot(x, avg_y, linestyle = '-', label = "average\n(exclude outliers)")
        plt.plot(x,stdp,linestyle = '--', label = "std+") 
        plt.plot(x,stdn,linestyle = '--', label = "std-") 
           
    #plt.show()
    plt.savefig(".work/J.png", dpi = 200)
    plt.clf()
    plt.close("all")

    return [avg,(y_stdp-avg),mean,mean_std]

def getT0Statistics(file, mask):
    result = np.zeros((len(file), 5))
    
    for i, filename in enumerate(file):
        with open(filename, 'r') as f:
            data = f.readlines()
            
        # check header here
        if data[0].rstrip() != "Samp#,Min,T,Date,iradiation PK 90%,Mass,T0,T0_SIGMA,R^2":
            raise Exception("Wrong data format!")

        for j in range(5):
            result[i, j] = float(data[j+1].split(',')[6])

    # calculate statistics
    statistics = np.zeros((5, 2))

    for i in range(5):
        statistics[i, 0] = np.mean(result[:, i])
        statistics[i, 1] = np.std(result[:, i])
        for j in range(len(result)):
            if abs(result[j,i] - statistics[i,0]) > (statistics[i,1]/2)+statistics[i,0] :
                mask[j] = 0

    k = 0
    for i in range(len(result)):
        if mask[i] == 0:
            result = np.delete(result,i-k,0)             
            k +=1

    restatistics = np.zeros((5, 2))

    for i in range(5):
        restatistics[i, 0] = np.mean(result[:, i])
        restatistics[i, 1] = np.std(result[:, i])
    
    n = len(result)
    
    # plot T0 distribution
    fig, axs = plt.subplots(1, 5, figsize = (12,4))
    for i in range(5):
        axs[i].plot(np.zeros(len(result)), result[:, i], marker = 'x', markersize = 10, linestyle = 'None')
        axs[i].errorbar(0, restatistics[i, 0], yerr = restatistics[i, 1], color = 'k', capthick = 2, capsize = 3, marker = '_', markersize = 15)
        axs[i].set_aspect(7/axs[i].get_data_ratio())
        axs[i].axes.get_xaxis().set_visible(False)  # remove the x-axis and its ticks
        axs[i].set_title("Ar {}".format(36+i))

    #plt.show()
    plt.savefig(".work/T0S.png", dpi = 200)
    plt.clf()
    plt.close("all")

    return restatistics,mask,statistics,n

def REgetT0Statistics(file, mask):
    result = np.zeros((len(file), 5))
    
    for i, filename in enumerate(file):
        with open(filename, 'r') as f:
            data = f.readlines()
            
        # check header here
        if data[0].rstrip() != "Samp#,Min,T,Date,iradiation PK 90%,Mass,T0,T0_SIGMA,R^2":
            raise Exception("Wrong data format!")

        for j in range(5):
            result[i, j] = float(data[j+1].split(',')[6])

    # calculate statistics
    k = 0
    for i in range(len(result)):
        if mask[i] == 0:
            result = np.delete(result,i-k,0)             
            k +=1
       
    n = len(result)
    statistics = np.zeros((5, 2))

    for i in range(5):
        statistics[i, 0] = np.mean(result[:, i])
        statistics[i, 1] = np.std(result[:, i])
    
    # plot T0 distribution
    fig, axs = plt.subplots(1, 5, figsize = (12,4))
    for i in range(5):
        axs[i].plot(np.zeros(len(result)), result[:, i], marker = 'x', markersize = 10, linestyle = 'None')
        axs[i].errorbar(0, statistics[i, 0], yerr = statistics[i, 1], color = 'k', capthick = 2, capsize = 3, marker = '_', markersize = 15)
        axs[i].set_aspect(7/axs[i].get_data_ratio())
        axs[i].axes.get_xaxis().set_visible(False)  # remove the x-axis and its ticks
        axs[i].set_title("Ar {}".format(36+i))

    #plt.show()
    plt.savefig(".work/T0S.png", dpi = 200)
    plt.clf()
    plt.close("all")

    return statistics,n

pair_indices = [[3, 4], [0, 4], [3, 0], [4, 0], [2, 0]]
#               39/40    36/40   39/36   40/36   38/36
def calculateMassRatio(mass_filename, background_filename, OGD):
    raw = np.zeros((5, 2))
    preline = np.zeros((5,2))

    with open(mass_filename, 'r') as f:
        data = f.readlines()
       
    # check header here
    if data[0].rstrip() != "Samp#,Min,T,Date,iradiation PK 90%,Mass,T0,T0_SIGMA,R^2":
        raise Exception("Wrong data format!")
       
    info = (data[1].split(','))[0]  
    t = (data[1].split(','))[2]
    Min = (data[1].split(','))[1]
    PK = (data[1].split(','))[4]
    SPD_raw = data[1].split(',')[3]
    # Normalize date: '2023/4/18' or '2023/04/18' → date object
    SPD_parts = SPD_raw.strip().split('/')
    SPD = date(int(SPD_parts[0]), int(SPD_parts[1]), int(SPD_parts[2]))
    # OGD may be 'YYYYMMDD' or 'YYYY-MM-DD'
    ogd_str = OGD.strip().replace('-','')
    OGD = date(int(ogd_str[0:4]), int(ogd_str[4:6]), int(ogd_str[6:8]))
    T = SPD-OGD
    T = int(T.days)
   
   
    for i in range(5):
        raw[i, 0] = float(data[i+1].split(',')[6]) # T0
        raw[i, 1] = float(data[i+1].split(',')[7]) # T0_SIGMA

    with open(background_filename, 'r') as f:
        data = f.readlines()

    # check header here
    if data[0].rstrip() != "Samp#,Min,T,Date,iradiation PK 90%,Mass,T0,T0_SIGMA,R^2":
        raise Exception("Wrong data format!")

    for i in range(5):
        preline[i, 0] = float(data[i+1].split(',')[6]) # T0
        preline[i, 1] = float(data[i+1].split(',')[7]) # T0_SIGMA

    measurement = raw[:, 0] - preline[:, 0] # 36 37 38 39 40 (Measurement)
    measurement_std = np.sqrt(raw[:, 1]**2 + preline[:, 1]**2)
    
    decay_37 = np.exp(0.0198*T)
    decay_39 = np.exp(0.0000071*T)
    measurement[1] = measurement[1] * decay_37
    measurement_std[1] = measurement_std[1] * decay_37   # BUG FIX: sync sigma
    measurement[3] = measurement[3] * decay_39
    measurement_std[3] = measurement_std[3] * decay_39   # BUG FIX: sync sigma
   
    ratio = np.zeros(5)
    ratio_std = np.zeros(5)
    for i in range(5):
        y, x = pair_indices[i][0], pair_indices[i][1]
        ratio[i] = measurement[y]/measurement[x]
        ratio_std[i] = abs(ratio[i]) * np.sqrt((measurement_std[y]/measurement[y])**2 + (measurement_std[x]/measurement[x])**2)  # BUG FIX: abs()

    return [raw[:, 0], measurement, measurement_std, ratio, ratio_std,info,t,Min,PK]

def calculateSlatCa(salt):
    ratio = np.zeros((2,2))

    with open(salt, 'r') as f:
        data = f.readlines()

    # check header here
    if data[0].rstrip() != "Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma":
        raise Exception("Wrong data format!")

    Ar36 = float(data[1].split(',')[6])    
    Ar36_std = float(data[1].split(',')[7])
    Ar37 = float(data[2].split(',')[6])    
    Ar37_std = float(data[2].split(',')[7])
    Ar39 = float(data[4].split(',')[6])    
    Ar39_std = float(data[4].split(',')[7])
    air = float(data[5].split(',')[6])
    air_std = float(data[5].split(',')[7])
    
    ratio[0,0] = (Ar36-air/298.56)/Ar37
    ratio[0,1] = ratio[0,0]*np.sqrt(((Ar36_std + air_std/298.56)/(Ar36 - air/298.56))**2 + (Ar37_std/Ar37)**2)
    ratio[1,0] = Ar39/Ar37
    ratio[1,1] = ratio[1,0]*np.sqrt((Ar39_std/Ar39)**2 + (Ar37_std/Ar37)**2)
    info = (data[1].split(','))[0]
    
    return ratio,info

def calculateSlatK(salt):
    ratio = np.zeros((3,2))

    with open(salt, 'r') as f:
        data = f.readlines()

    # check header here
    if data[0].rstrip() != "Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma":
        raise Exception("Wrong data format!")

    Ar36 = float(data[1].split(',')[6])    
    Ar36_std = float(data[1].split(',')[7])
    Ar40 = float(data[5].split(',')[6])    
    Ar40_std = float(data[5].split(',')[7])
    Ar39 = float(data[4].split(',')[6])    
    Ar39_std = float(data[4].split(',')[7])
    Ar38 = float(data[3].split(',')[6])
    Ar38_std = float(data[3].split(',')[7])
    Ar37 = float(data[2].split(',')[6])
    Ar37_std = float(data[2].split(',')[7])

    ratio[0,0] = (Ar40-Ar36*298.56)/Ar39
    ratio[0,1] = ratio[0,0]*np.sqrt(((Ar40_std + Ar36_std*298.56) / (Ar40 - Ar36*298.56))**2 + (Ar39_std/Ar39)**2)
    ratio[1,0] = Ar38/Ar39
    ratio[1,1] = ratio[1,0]*np.sqrt((Ar38_std/Ar38)**2 + (Ar39_std/Ar39)**2)
    ratio[2,0] = Ar39/Ar37
    ratio[2,1] = ratio[2,0]*np.sqrt((Ar39_std/Ar39)**2 + (Ar37_std/Ar37)**2)
    info = (data[1].split(','))[0]

    return ratio,info

def getJVolumeStatistics(file, t,t_std,constants):
    l = 5.531*0.0000000001
    l_std = 0.0135*0.0000000001
    # collect data
    data = np.zeros((5, 2))

    with open(file,'r') as f:
        tmp_data = f.readlines()
    
    # check header here
    if tmp_data[0].rstrip() != "Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma":
        raise Exception("Wrong data format!")

    for i in range(5):
        data[i, 0] = float(tmp_data[i+1].split(',')[6])
        data[i, 1] = float(tmp_data[i+1].split(',')[7])
    # Ar component calculation
    Ar_37_m = data[1, 0]
    Ar_37_m_std = data[1, 1]
    Ar_37_Ca = Ar_37_m
    Ar_37_Ca_std = Ar_37_m_std

    Ar_36_m = data[0, 0]
    Ar_36_m_std = data[0, 1]
    Ar_36_Ca = Ar_37_Ca * constants[2] #36Ar/37Ar(ca)
    Ar_36_Air = Ar_36_m - Ar_36_Ca

    Ar_39_m = data[3, 0]
    Ar_39_m_std = data[3, 1]
    Ar_39_Ca = Ar_37_Ca * constants[0] #39Ar/37Ar(ca)
    Ar_39_Ca_std = (Ar_37_Ca_std/Ar_37_Ca + constants[1]/constants[0]) * Ar_39_Ca #39Ar/37Ar(ca) std / 39Ar/37Ar(ca)
    Ar_39_K = Ar_39_m - Ar_39_Ca
    Ar_39_K_std = minusSigma(Ar_39_m_std, Ar_39_Ca_std)

    Ar_40_m = data[4, 0]
    Ar_40_m_std = data[4, 1]
    Ar_40_air = Ar_36_Air * constants[12] #40/36(a)
    Ar_40_K = Ar_39_K * constants[4] #40Ar/39Ar(k)
    Ar_40_radioactive = Ar_40_m - Ar_40_air - Ar_40_K
    
    Ar_39_K_40_r_ratio =  Ar_40_radioactive/Ar_39_K
    
    C1, C2, C4 = constants[12], constants[2], constants[0] ##40/36(a) 36Ar/37Ar(ca) 39Ar/37Ar(ca)
    G = Ar_40_m / Ar_39_m
    G_std = G*(Ar_40_m_std/Ar_40_m + Ar_39_m_std/Ar_39_m)
    B = Ar_36_m / Ar_39_m
    B_std = B*(Ar_36_m_std/Ar_36_m + Ar_39_m_std/Ar_39_m)
    D = Ar_37_m / Ar_39_m
    D_std = D*(Ar_37_m_std/Ar_37_m + Ar_39_m_std/Ar_39_m)
    F_std = np.sqrt(G_std**2 + (C1*B_std)**2 + ((C4*G - C1*C4*B + C1*C2)*D_std)**2)
    
    # J calcuation
    J = (np.exp(l*t)-1)/(Ar_40_radioactive/Ar_39_K) 
    v1 = l_std**2*(t*np.exp(l*t)/Ar_39_K_40_r_ratio)**2
    v2 = t_std ** 2 * (l * np.exp(l * t) / Ar_39_K_40_r_ratio) ** 2
    v3 = F_std ** 2 * ((np.exp(l * t)) - 1 / Ar_39_K_40_r_ratio ** 2) ** 2
    J_std = pow(v1 + v2 + v3, 0.5)
    J_int = pow(v3, 0.5)
    # FIX: Ca/K = 37Ar_ca × R / 39Ar_k  (R=0.52, lab calibration factor)
    # 原本 (Ar_39_K*0.52)/Ar_37_Ca 是 K/Ca，分子分母接反了
    _CaK     = (Ar_37_Ca * 0.52) / Ar_39_K if Ar_39_K != 0 else 0.0
    _CaK_std = _CaK * (Ar_37_Ca_std / Ar_37_Ca + Ar_39_K_std / Ar_39_K) if (Ar_37_Ca != 0 and Ar_39_K != 0) else 0.0
    return [Ar_36_Air,Ar_37_Ca,Ar_39_K,Ar_40_radioactive,Ar_40_radioactive/Ar_40_m*100,Ar_39_K/Ar_39_m*100,_CaK,_CaK_std,J,J_std,J_int]

def calcAge(measurement_filename, J, J_std, J_int, constants):
    """
    Compute Ar/Ar age + all Ar component breakdown for one step.

    v3.7.4: Restored from V3.4.1 archive after the v3.7.x release HEAD shipped a
    truncated version (function ended mid-statement at `Ar_39_Ca = ...`).
    Linear-error-propagation style preserved (same as getJVolumeStatistics
    sister function).  Math review (Ca/K constant, quadrature vs linear σ,
    36Ar(Cl) atmospheric correction) deferred to later release after
    discussion with advisor — see notes/pyADR_math_audit_v1.md.

    Returns 59-element list; key indices:
       18 Ar_39_K, 19 Ar_39_K_std
       24 Ar_40_radioactive, 25 std
       36 F, 37 F_std
       46 T (Age in years), 47 T_std
       48 J_int, 49 T_int
    """
    # collect data
    data = np.zeros((5, 2))

    with open(measurement_filename, 'r') as f:
        tmp_data = f.readlines()

    # check header here
    if tmp_data[0].rstrip() != "Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma":
        raise Exception("Wrong data format!")

    info = (tmp_data[1].split(',')[0])
    t = (tmp_data[1].split(',')[1])
    Min = (tmp_data[1].split(',')[2])
    PK = (tmp_data[1].split(',')[3])

    for i in range(5):
        data[i, 0] = float(tmp_data[i+1].split(',')[6])
        data[i, 1] = float(tmp_data[i+1].split(',')[7])

    # Ar component calculation
    Ar_37_m = data[1, 0]
    Ar_37_m_std = data[1, 1]
    Ar_37_Ca = Ar_37_m
    Ar_37_Ca_std = Ar_37_m_std

    Ar_36_m = data[0, 0]
    Ar_36_m_std = data[0, 1]
    Ar_36_Ca = Ar_37_Ca * constants[2] #36Ar/37Ar(ca)
    Ar_36_Ca_std = (Ar_37_Ca_std/Ar_37_Ca + constants[3]/constants[2]) * Ar_36_Ca #36Ar/37Ar(ca) std / 36Ar/37Ar(ca)
    Ar_36_Air = Ar_36_m - Ar_36_Ca
    Ar_36_Air_std = minusSigma(Ar_36_m_std, Ar_36_Ca_std)

    Ar_39_m = data[3, 0]
    Ar_39_m_std = data[3, 1]
    Ar_39_Ca = Ar_37_Ca * constants[0] #39Ar/37Ar(ca)
    Ar_39_Ca_std = (Ar_37_Ca_std/Ar_37_Ca + constants[1]/constants[0]) * Ar_39_Ca #39Ar/37Ar(ca) std /39Ar/37Ar(ca)
    Ar_39_K = Ar_39_m - Ar_39_Ca
    Ar_39_K_std = minusSigma(Ar_39_m_std, Ar_39_Ca_std)

    Ar_38_m = data[2, 0]
    Ar_38_m_std = data[2, 1]
    Ar_38_K = Ar_39_K * constants[6] #38Ar/39Ar(k)
    Ar_38_K_std = (Ar_39_K_std/Ar_39_K + constants[7]/constants[6]) * Ar_38_K #38Ar/39Ar(k) std / 38Ar/39Ar(k)
    Ar_38_Air = Ar_38_m - Ar_38_K
    Ar_38_Air_std = minusSigma(Ar_38_m_std, Ar_38_K_std)

    Ar_40_m = data[4, 0]
    Ar_40_m_std = data[4, 1]
    Ar_40_air = Ar_36_Air * constants[12] #40/36(a)
    Ar_40_air_std = (Ar_36_Air_std/Ar_36_Air + constants[13]/constants[12]) * Ar_40_air #40/36(a) std / 40/36(a)
    Ar_40_K = Ar_39_K * constants[4] #40Ar/39Ar(k)
    Ar_40_K_std = (Ar_39_K_std/Ar_39_K + constants[5]/constants[4]) * Ar_40_K #40Ar/39Ar(k) std / 40Ar/39Ar(k)
    Ar_40_radioactive = Ar_40_m - Ar_40_air - Ar_40_K
    Ar_40_radioactive_std = np.sqrt(Ar_40_m_std**2 + Ar_40_air_std**2 + Ar_40_K_std**2)
    Ar_40_radioactive_ratio = Ar_40_radioactive / data[4, 0]


    # ratio calculation
    Ar_39_K_40_r_ratio =  Ar_39_K / Ar_40_radioactive
    Ar_39_K_40_r_ratio_std = Ar_39_K_40_r_ratio*(Ar_39_K_std/Ar_39_K + Ar_40_radioactive_std/Ar_40_radioactive)
    Ar_36_Air_40_r_ratio = Ar_36_Air / Ar_40_radioactive
    Ar_36_Air_40_r_ratio_std = Ar_36_Air_40_r_ratio*(Ar_36_Air_std/Ar_36_Air + Ar_40_radioactive_std/Ar_40_radioactive)
    Ar_39_K_36_Air = Ar_39_K / Ar_36_Air
    Ar_39_K_36_Air_std = Ar_39_K_36_Air*(Ar_39_K_std/Ar_39_K + Ar_36_Air_std/Ar_36_Air)

    # Age calculation
    C1, C2, C3, C4 = constants[12], constants[2], constants[4], constants[0] #40/36(a) 36Ar/37Ar(ca) 40Ar/39Ar(k) 39Ar/37Ar(ca)
    G = Ar_40_m / Ar_39_m
    G_std = G*(Ar_40_m_std/Ar_40_m + Ar_39_m_std/Ar_39_m)
    B = Ar_36_m / Ar_39_m
    B_std = B*(Ar_36_m_std/Ar_36_m + Ar_39_m_std/Ar_39_m)
    D = Ar_37_m / Ar_39_m
    D_std = D*(Ar_37_m_std/Ar_37_m + Ar_39_m_std/Ar_39_m)
    F = Ar_40_radioactive / Ar_39_K
    F_std = np.sqrt(G_std**2 + (C1*B_std)**2 + ((C4*G - C1*C4*B + C1*C2)*D_std)**2)

    T = np.log(1 + J*F) / constants[16] #Lambda
    T_std = np.sqrt((J**2 * F_std**2 + F**2 * J_std**2)/ ((constants[16]*(1+F*J))**2)) #Lambda
    T_int = np.sqrt((J**2 * F_std**2 + F**2 * J_int**2)/ ((constants[16]*(1+F*J))**2)) #Lambda

    return [Ar_36_m, Ar_36_m_std, Ar_36_Air, Ar_36_Air_std, Ar_36_Ca, Ar_36_Ca_std,
            Ar_37_m, Ar_37_m_std, Ar_37_Ca, Ar_37_Ca_std,
            Ar_38_m, Ar_38_m_std, Ar_38_Air, Ar_38_Air_std, Ar_38_K, Ar_38_K_std,
            Ar_39_m, Ar_39_m_std, Ar_39_K, Ar_39_K_std, Ar_39_Ca, Ar_39_Ca_std,
            Ar_40_m, Ar_40_m_std, Ar_40_radioactive, Ar_40_radioactive_std, Ar_40_air, Ar_40_air_std, Ar_40_K, Ar_40_K_std,
            Ar_39_K_40_r_ratio, Ar_39_K_40_r_ratio_std, Ar_36_Air_40_r_ratio, Ar_36_Air_40_r_ratio_std, Ar_39_K_36_Air, Ar_39_K_36_Air_std,
            F, F_std, G, G_std, B, B_std, D, D_std,
            J, J_std,
            T, T_std,
            J_int, T_int,
            Ar_40_radioactive_ratio, C1, C2, C3, C4, info, t, Min, PK
            ]


# ============================================================
#  Stack Plot  (DFS)  &  Summary Figure  (DFM)
# ============================================================


def _get_style(style='pyADR'):
    """Return color/appearance dict for the given plot style."""
    if style == 'classic':
        return dict(
            age='white', cak='white', clk='white',
            atm='white', iso_dot='black',
            edge='black', lw=0.8, alpha=1.0,
            mean_color='black', mean_ls='-',
            grid=False, bg='white',
            classic=True,
        )
    else:  # pyADR (default)
        return dict(
            age='#4040a0', cak='#6a0dad', clk='teal',
            atm='#b05000', iso_dot='#1a5a8a',
            edge='black', lw=0.5, alpha=1.0,
            mean_color='navy', mean_ls='--',
            grid=True, bg=None,
            classic=False,
        )

def _read_sh_rows(file):
    """Return (header_col_dict, data_rows, stepw, y_age, y_age_err, mask_col)."""
    import numpy as np
    with open(file, 'r', encoding='utf-8-sig', errors='ignore') as f:
        data = f.readlines()
    header = data[0].rstrip().split(',')
    col = {name.strip(): i for i, name in enumerate(header)}
    rows = []
    for line in data[1:]:
        r = line.split(',')
        if len(r) > 17 and r[17].strip() not in ('nan', ''):
            rows.append(r)
    n = len(rows)
    stepw   = np.array([float(rows[i][22])   for i in range(n)])
    y_age   = np.array([float(rows[i][17])   for i in range(n)])
    y_err   = np.array([float(rows[i][18])   for i in range(n)])
    return col, rows, stepw, y_age, y_err, n


def _draw_step_bars(ax, stepw, y_vals, y_errs, mask, color='purple', alpha=1.0,
                    edge='black', lw=0.5,
                    step_groups=None, group_colors=None):
    """Draw step-heating rectangles + connecting lines + exclusion X.

    step_groups : optional dict {step_idx -> group_num} for per-bar coloring.
    group_colors: optional list, indexed by group_num-1, gives bar fill colour.
    """
    import matplotlib.patches as patches
    import numpy as np
    n = len(stepw)
    j = 0.0
    for i in range(n):
        w = stepw[i]
        bot = y_vals[i] - y_errs[i]
        ht  = y_errs[i] * 2
        # Pick fill colour: group colour if assigned, else default
        fc = color
        if step_groups and i in step_groups and group_colors:
            gi = step_groups[i] - 1
            if 0 <= gi < len(group_colors):
                fc = group_colors[gi]
        rect = patches.Rectangle((j, bot), w, ht,
                                  edgecolor=edge, facecolor=fc,
                                  linewidth=lw, alpha=alpha)
        ax.add_patch(rect)
        if i < n - 1:
            ax.plot([j + w, j + w], [y_vals[i], y_vals[i + 1]],
                    'k-', linewidth=0.5)
        if i < len(mask) and mask[i] == 0:
            ax.plot(j + w / 2, y_vals[i], 'rx', markersize=10, markeredgewidth=1.5)
        j += w
    ax.set_xlim(0, 100)


def getDegasPlot(file, mask, constants,
                 xlim=None, ylim=None, legend_name=None,
                 show_legend=True, log_y=True,
                 show_all_components=False,
                 components_filter=None,
                 show_errorbars=False,
                 show_step_labels=True,
                 style='pyADR'):
    """
    Degassing pattern: per-step Ar component amounts vs temperature.

    Default (show_all_components=False): 5 isotope totals
        36Ar(m) = a+c+ca+cl   (blue)
        37Ar(Ca)              (green)
        38Ar(m) = a+c+k+ca+cl (orange)
        39Ar(K)               (red)
        40Ar(r)               (purple)
    show_all_components=True: 16 individual components, color-grouped by isotope.
    Saved to .work/DFD.png
    """
    import os
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # Use same convention as other plot functions: .work next to Utilities.py
    outdir = os.path.join(os.path.dirname(__file__), ".work")
    os.makedirs(outdir, exist_ok=True)

    with open(file, 'r', encoding='utf-8-sig', errors='ignore') as f:
        data = f.readlines()
    header = data[0].rstrip().split(',')
    col = {name.strip(): i for i, name in enumerate(header)}

    # Strip blank trailing lines, drop nan-Age rows
    rows = []
    for line in data[1:]:
        if not line.strip():
            continue
        parts = line.split(',')
        if len(parts) > 17 and parts[17].strip() != "nan":
            rows.append(parts)

    n = len(rows)
    if n == 0:
        # nothing to plot — emit empty
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        ax.set_xlabel("Temperature (°C)")
        ax.set_ylabel("Ar amount (V)")
        ax.set_title("(no data)")
        fig.savefig(os.path.join(outdir, "DFD.png"), dpi=300, facecolor='white')
        plt.close('all')
        return {"path": os.path.join(outdir, "DFD.png"), "step_data": {"DFD": []}}

    # Apply mask: drop steps where mask[i] == 0
    mask = np.asarray(mask, dtype=float).copy()
    if mask.size < n:
        mask = np.pad(mask, (0, n - mask.size), constant_values=1.0)
    elif mask.size > n:
        mask = mask[:n]

    # Temperature axis
    T = np.array([float(r[col.get('deg C', 3)]) for r in rows])

    # Component definitions  (key, csv_name, isotope_group)
    if show_all_components:
        comp_defs = [
            ('36Ar(a)',  '36Ar(a)',  '36'),
            ('36Ar(c)',  '36Ar(c)',  '36'),
            ('36Ar(ca)', '36Ar(ca)', '36'),
            ('36Ar(cl)', '36Ar(cl)', '36'),
            ('37Ar(ca)', '37Ar(ca)', '37'),
            ('38Ar(a)',  '38Ar(a)',  '38'),
            ('38Ar(c)',  '38Ar(c)',  '38'),
            ('38Ar(k)',  '38Ar(k)',  '38'),
            ('38Ar(ca)', '38Ar(ca)', '38'),
            ('38Ar(cl)', '38Ar(cl)', '38'),
            ('39Ar(k)',  '39Ar(k)',  '39'),
            ('39Ar(ca)', '39Ar(ca)', '39'),
            ('40Ar(r)',  '40Ar(r)',  '40'),
            ('40Ar(a)',  '40Ar(a)',  '40'),
            ('40Ar(c)',  '40Ar(c)',  '40'),
            ('40Ar(k)',  '40Ar(k)',  '40'),
        ]
    else:
        comp_defs = []  # built below from sums

    # Find the "Degassing Patterns" section start (column index)
    # All Ar-component columns appear in CSV under that section
    def _read_col(name, default_idx=None):
        """Read one column robustly: prefer Degassing Patterns occurrence (later index)."""
        # Find ALL indices for this column name; the degassing-pattern entries are at later indices
        idxs = [i for i, h in enumerate(header) if h.strip() == name.strip()]
        if not idxs:
            if default_idx is not None:
                return default_idx
            return None
        # use the LAST occurrence (Degassing Patterns section)
        return idxs[-1]

    def _series(name):
        ci = _read_col(name)
        if ci is None:
            return np.zeros(n)
        out = np.zeros(n)
        for i, r in enumerate(rows):
            try:
                out[i] = float(r[ci])
            except (ValueError, IndexError):
                out[i] = 0.0
        return out

    def _series_err(name):
        std_name = name + '_std' if not name.endswith('_std') else name
        idxs = [i for i, h in enumerate(header) if h.strip() == std_name.strip()]
        if not idxs:
            return np.zeros(n)
        ci = idxs[-1]
        out = np.zeros(n)
        for i, r in enumerate(rows):
            try:
                out[i] = abs(float(r[ci]))
            except (ValueError, IndexError):
                out[i] = 0.0
        return out

    def _sum_with_err(*names):
        vals = np.zeros(n)
        var  = np.zeros(n)
        for nm in names:
            v = _series(nm)
            e = _series_err(nm)
            vals = vals + v
            var  = var + e * e
        return vals, np.sqrt(var)

    # Build series
    isotope_color = {
        '36': '#1565C0',  # blue
        '37': '#2E7D32',  # green
        '38': '#E65100',  # orange
        '39': '#C62828',  # red
        '40': '#6A1B9A',  # purple
    }
    # When showing 16 components, fade lightness within each isotope group
    isotope_palette = {
        '36': ['#0D47A1', '#1976D2', '#42A5F5', '#90CAF9'],
        '37': ['#2E7D32'],
        '38': ['#BF360C', '#E64A19', '#FB8C00', '#FFB74D', '#FFCC80'],
        '39': ['#B71C1C', '#EF5350'],
        '40': ['#4A148C', '#7B1FA2', '#AB47BC', '#CE93D8'],
    }

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)

    if not show_all_components:
        # 5 isotope totals (all use Ar(m) sums)
        s36m, e36m = _sum_with_err('36Ar(a)', '36Ar(c)', '36Ar(ca)', '36Ar(cl)')
        s37,  e37  = _sum_with_err('37Ar(ca)')
        s38m, e38m = _sum_with_err('38Ar(a)', '38Ar(c)', '38Ar(k)', '38Ar(ca)', '38Ar(cl)')
        s39m, e39m = _sum_with_err('39Ar(k)', '39Ar(ca)')
        s40m, e40m = _sum_with_err('40Ar(r)', '40Ar(a)', '40Ar(c)', '40Ar(k)')
        series_to_plot = [
            ('³⁶Ar(m)', s36m, isotope_color['36'], e36m),
            ('³⁷Ar(m)', s37,  isotope_color['37'], e37),
            ('³⁸Ar(m)', s38m, isotope_color['38'], e38m),
            ('³⁹Ar(m)', s39m, isotope_color['39'], e39m),
            ('⁴⁰Ar(m)', s40m, isotope_color['40'], e40m),
        ]
    else:
        # 16 individual components (with err arrays)
        series_to_plot = []
        idx_per_iso = {}
        for label, csv_name, iso in comp_defs:
            shade_list = isotope_palette[iso]
            k = idx_per_iso.get(iso, 0)
            color = shade_list[k % len(shade_list)]
            idx_per_iso[iso] = k + 1
            pretty = (label.replace('36Ar', '³⁶Ar')
                           .replace('37Ar', '³⁷Ar')
                           .replace('38Ar', '³⁸Ar')
                           .replace('39Ar', '³⁹Ar')
                           .replace('40Ar', '⁴⁰Ar'))
            series_to_plot.append((pretty, _series(csv_name), color, _series_err(csv_name)))

    # If components_filter is given, override series_to_plot with the union of
    # 5 Ar(m) sums + 16 individuals, then filter to user-selected labels.
    if components_filter is not None:
        # Build all 21 candidate series
        s36m_v, s36m_e = _sum_with_err('36Ar(a)', '36Ar(c)', '36Ar(ca)', '36Ar(cl)')
        s37m_v, s37m_e = _sum_with_err('37Ar(ca)')
        s38m_v, s38m_e = _sum_with_err('38Ar(a)', '38Ar(c)', '38Ar(k)', '38Ar(ca)', '38Ar(cl)')
        s39m_v, s39m_e = _sum_with_err('39Ar(k)', '39Ar(ca)')
        s40m_v, s40m_e = _sum_with_err('40Ar(r)', '40Ar(a)', '40Ar(c)', '40Ar(k)')
        all_series = [
            ('³⁶Ar(m)', s36m_v, isotope_color['36'], s36m_e),
            ('³⁷Ar(m)', s37m_v, isotope_color['37'], s37m_e),
            ('³⁸Ar(m)', s38m_v, isotope_color['38'], s38m_e),
            ('³⁹Ar(m)', s39m_v, isotope_color['39'], s39m_e),
            ('⁴⁰Ar(m)', s40m_v, isotope_color['40'], s40m_e),
        ]
        comp_full_defs = [
            ('36Ar(a)',  '36'), ('36Ar(c)',  '36'), ('36Ar(ca)', '36'), ('36Ar(cl)', '36'),
            ('37Ar(ca)', '37'),
            ('38Ar(a)',  '38'), ('38Ar(c)',  '38'), ('38Ar(k)',  '38'), ('38Ar(ca)', '38'), ('38Ar(cl)', '38'),
            ('39Ar(k)',  '39'), ('39Ar(ca)', '39'),
            ('40Ar(r)',  '40'), ('40Ar(a)',  '40'), ('40Ar(c)',  '40'), ('40Ar(k)',  '40'),
        ]
        idx_per_iso = {}
        for csv_name, iso in comp_full_defs:
            shade_list = isotope_palette[iso]
            k = idx_per_iso.get(iso, 0)
            color = shade_list[k % len(shade_list)]
            idx_per_iso[iso] = k + 1
            pretty = (csv_name.replace('36Ar', '³⁶Ar')
                              .replace('37Ar', '³⁷Ar')
                              .replace('38Ar', '³⁸Ar')
                              .replace('39Ar', '³⁹Ar')
                              .replace('40Ar', '⁴⁰Ar'))
            all_series.append((pretty, _series(csv_name), color, _series_err(csv_name)))
        # Filter
        flt = set(components_filter)
        series_to_plot = [s for s in all_series if s[0] in flt]

    # Plot each series; apply mask for hidden steps
    for entry in series_to_plot:
        label, y, color = entry[0], entry[1], entry[2]
        yerr = entry[3] if len(entry) >= 4 else np.zeros_like(y)
        valid = (mask == 1) & np.isfinite(y) & (y > 0 if log_y else np.ones_like(y, dtype=bool))
        if not valid.any():
            continue
        if show_errorbars:
            lo = yerr[valid].copy()
            if log_y:
                lo = np.minimum(lo, np.maximum(y[valid] * 0.999, 0.0))
            ax.errorbar(T[valid], y[valid],
                        yerr=[lo, yerr[valid]],
                        fmt='o-', markersize=4, linewidth=1.4,
                        capsize=3, color=color, label=label,
                        ecolor=color, elinewidth=0.8, alpha=0.9)
        else:
            ax.plot(T[valid], y[valid], marker='o', markersize=4,
                    linewidth=1.4, color=color, label=label)
        masked_pts = (mask == 0)
        if masked_pts.any():
            yfin = np.where(np.isfinite(y), y, np.nan)
            ax.scatter(T[masked_pts], yfin[masked_pts], marker='x',
                       s=40, c='red', zorder=10)

    # Step number labels at the top of the plot frame (above top spine)
    if show_step_labels:
        for i in range(n):
            if mask[i] == 0:
                continue
            ax.annotate(str(i + 1),
                        xy=(T[i], 1.0), xycoords=('data', 'axes fraction'),
                        xytext=(0, 4), textcoords='offset points',
                        ha='center', va='bottom',
                        fontsize=8, color='#444', clip_on=False)

    if log_y:
        ax.set_yscale('log')
    if xlim is not None:
        ax.set_xlim(xlim[0], xlim[1])
    if ylim is not None:
        ax.set_ylim(ylim[0], ylim[1])

    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Ar amount (V)")

    # Style frame
    st = _get_style(style)
    if st.get('classic'):
        ax.set_facecolor('white')
        ax.tick_params(which='both', direction='out',
                       top=True, right=True, bottom=True, left=True)
        ax.minorticks_on()
        for sp in ax.spines.values():
            sp.set_visible(True); sp.set_linewidth(1.0); sp.set_color('black')
    else:
        ax.set_facecolor('none')
        ax.tick_params(which='both', direction='out', top=False, right=False)

    if show_legend:
        ax.legend(loc='best', fontsize=8, ncol=2 if show_all_components else 1, frameon=False)

    if legend_name:
        ax.set_title(legend_name)

    try:
        fig.tight_layout()
    except Exception:
        pass
    fig.savefig(os.path.join(outdir, "DFD.png"), dpi=300,
                facecolor='white' if st.get('classic') else 'none')
    plt.close('all')

    # Build step_data for hover
    step_data_dfd = []
    for entry in series_to_plot:
        label, y = entry[0], entry[1]
        total_y = float(np.nansum(np.where(np.isfinite(y) & (y > 0), y, 0.0)))
        for i in range(n):
            if mask[i] == 0:
                continue
            v = float(y[i]) if np.isfinite(y[i]) else float('nan')
            if total_y > 0 and np.isfinite(v) and v > 0:
                pct = v / total_y * 100.0
            else:
                pct = float('nan')
            step_data_dfd.append((label, float(T[i]), v, pct, int(i + 1)))

    actual_xlim = tuple(float(v) for v in ax.get_xlim())
    actual_ylim = tuple(float(v) for v in ax.get_ylim())
    _ax_pos = ax.get_position()
    axes_bbox = (_ax_pos.x0, _ax_pos.y0, _ax_pos.x1, _ax_pos.y1)

    return {
        "path": os.path.join(outdir, "DFD.png"),
        "step_data": {"DFD": step_data_dfd},
        "actual_xlim": {"DFD": actual_xlim},
        "actual_ylim": {"DFD": actual_ylim},
        "axes_bbox":   {"DFD": axes_bbox},
    }


def getStackPlot(file, mask, constants, top='Ca/K', log_scale=True,
                 h_ratio=(1, 4), legend_name=None, ylim_age=None, style='pyADR',
                 xlim_top=None, ylim_top=None, xlim_bot=None, ylim_bot=None,
                 step_groups=None, group_colors=None):
    """
    Stack figure: ratio panel (top) + Age spectrum (bottom).
    Saved to .work/DFS.png
    top       : 'Ca/K' or 'Cl/K'
    xlim_top/ylim_top : (min,max) for top ratio panel
    xlim_bot/ylim_bot : (min,max) for bottom age panel  (ylim_bot overrides ylim_age)
    """
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    col, rows, stepw, y_age, y_err, n = _read_sh_rows(file)

    # ── ratio data ──────────────────────────────────────────────
    y_ratio     = np.zeros(n)
    y_ratio_err = np.zeros(n)
    if top == 'Ca/K':
        cak_idx = col.get('Ca/K', 23)
        cak_s   = col.get('Ca/K_std', 24)
        for i in range(n):
            try:
                y_ratio[i]     = float(rows[i][cak_idx])
                y_ratio_err[i] = float(rows[i][cak_s]) if cak_s < len(rows[i]) else 0.0
            except Exception:
                pass
        ratio_color  = _get_style(style)['cak']
        ratio_label  = 'Ca/K'
        formula_hint = r'Ca/K $= (^{37}\!\mathrm{Ar}_{Ca}/^{39}\!\mathrm{Ar}_K)\times 0.55$'
    else:  # Cl/K
        CLK = 0.22
        a38_idx = col.get('38Ar(cl)'); a38s_idx = col.get('38Ar(cl)_std')
        a39_idx = col.get('39Ar(k)');  a39s_idx = col.get('39Ar(k)_std')
        for i in range(n):
            try:
                a38 = float(rows[i][a38_idx]); a38s = float(rows[i][a38s_idx]) if a38s_idx else 0
                a39 = float(rows[i][a39_idx]); a39s = float(rows[i][a39s_idx]) if a39s_idx else 0
                if a39 != 0:
                    y_ratio[i] = CLK * a38 / a39
                    if a38 != 0:
                        y_ratio_err[i] = abs(y_ratio[i]) * np.sqrt(
                            (a38s/a38)**2 + (a39s/a39)**2)
            except Exception:
                pass
        ratio_color  = _get_style(style)['clk']
        ratio_label  = 'Cl/K'
        formula_hint = r'Cl/K $= (^{38}\!\mathrm{Ar}_{Cl}/^{39}\!\mathrm{Ar}_K)\times 0.22$'

    # ── figure ──────────────────────────────────────────────────
    fig = plt.figure(figsize=(8, 8), dpi=150)
    gs  = gridspec.GridSpec(2, 1, height_ratios=list(h_ratio), hspace=0.05,
                            left=0.12, right=0.95, top=0.93, bottom=0.09)
    ax_top = fig.add_subplot(gs[0])
    ax_bot = fig.add_subplot(gs[1], sharex=ax_top)

    # top: ratio
    _st = _get_style(style)
    _draw_step_bars(ax_top, stepw, y_ratio, y_ratio_err, mask,
                    step_groups=step_groups, group_colors=group_colors,
                    color=ratio_color, edge=_st['edge'], lw=_st['lw'])
    if log_scale and np.any(y_ratio > 0):
        ax_top.set_yscale('log')
    ax_top.set_ylabel(ratio_label, fontsize=10)
    ax_top.tick_params(labelbottom=False)
    ax_top.text(0.01, 0.97, formula_hint, transform=ax_top.transAxes,
                ha='left', va='top', fontsize=7, color='#555', style='italic')
    if legend_name:
        ax_top.set_title(legend_name, fontsize=11)

    # bottom: age
    _draw_step_bars(ax_bot, stepw, y_age, y_err, mask,
                    step_groups=step_groups, group_colors=group_colors,
                    color=_st['age'], edge=_st['edge'], lw=_st['lw'])
    _ylim_bot = ylim_bot if ylim_bot else ylim_age
    if _ylim_bot:
        ax_bot.set_ylim(_ylim_bot)
    else:
        pad = 0.1 * max(float(np.nanmax(y_age + y_err) - np.nanmin(y_age - y_err)), 1.0)
        ax_bot.set_ylim(float(np.nanmin(y_age - y_err)) - pad,
                        float(np.nanmax(y_age + y_err)) + pad)
    ax_bot.set_xlabel('Cumulative $^{39}$Ar Released (%)', fontsize=10)
    ax_bot.set_ylabel('Age (Ma)', fontsize=10)

    # apply optional axis ranges
    if xlim_top is not None:
        ax_top.set_xlim(xlim_top)
    if ylim_top is not None:
        ax_top.set_ylim(ylim_top)
    if xlim_bot is not None:
        ax_bot.set_xlim(xlim_bot)

    # grid / background per style
    if _st.get('grid'):
        ax_top.grid(True, ls=':', lw=0.4, alpha=0.6)
        ax_bot.grid(True, ls=':', lw=0.4, alpha=0.6)

    # save
    import os
    outdir = os.path.join(os.path.dirname(__file__), ".work")
    os.makedirs(outdir, exist_ok=True)
    fig.savefig(os.path.join(outdir, "DFS.png"), dpi=300,
                facecolor=("white" if _st.get("classic") else "none"))
    plt.close('all')
    return os.path.join(outdir, "DFS.png")



# ============================================================
#  Summary Plot  (DFM)  - multi-panel: vertical or 2-col grid
# ============================================================
def getSummaryPlot(file, mask, constants, panels=None, legend_name=None,
                   style='pyADR', panel_limits=None, panel_legends=None,
                   layout='vertical', atm_ratio=298.56,
                   step_groups=None, group_colors=None,
                   show_group_fits=True, show_overall_fit=True):
    """
    Multi-panel summary figure.
    panels        : ordered list of keys among ['age','atm','cak','clk','iso']
    panel_limits  : {key: (xlim, ylim)}  -- xlim/ylim may be None
    panel_legends : {key: str}           -- per-panel title above each subplot
    layout        : 'vertical' (one column) or 'grid' (2-column;
                    odd last spans full width)
    legend_name   : figure-level title (suptitle)
    """
    import os, numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    if not panels:
        panels = ['age', 'atm', 'cak', 'clk', 'iso']
    panel_limits  = panel_limits  or {}
    panel_legends = panel_legends or {}
    _st = _get_style(style)

    col, rows, stepw, y_age, y_err, n = _read_sh_rows(file)

    def _col_arr(idx):
        out = np.full(n, np.nan)
        if idx is None:
            return out
        for i in range(n):
            try:
                out[i] = float(rows[i][idx])
            except Exception:
                pass
        return out

    # %40Ar* per step: col 19 = '40Ar(r)(%)' (NOT col 21 step-heating cumulative)
    atm_idx = col.get('40Ar(r)(%)', 19)
    y_atm   = _col_arr(atm_idx); y_atm_err = np.zeros(n)

    cak_idx = col.get('Ca/K', 23); cak_s = col.get('Ca/K_std', 24)
    y_cak   = _col_arr(cak_idx); y_cak_err = _col_arr(cak_s)

    CLK = 0.22
    a38_i = col.get('38Ar(cl)'); a38s_i = col.get('38Ar(cl)_std')
    a39_i = col.get('39Ar(k)');  a39s_i = col.get('39Ar(k)_std')
    y_clk = np.zeros(n); y_clk_err = np.zeros(n)
    for i in range(n):
        try:
            a38 = float(rows[i][a38_i]); a38s = float(rows[i][a38s_i]) if a38s_i else 0.0
            a39 = float(rows[i][a39_i]); a39s = float(rows[i][a39s_i]) if a39s_i else 0.0
            if a39 != 0:
                y_clk[i] = CLK * a38 / a39
                if a38 != 0:
                    y_clk_err[i] = abs(y_clk[i]) * np.sqrt((a38s/a38)**2 + (a39s/a39)**2)
        except Exception:
            pass

    # Inverse isochron: X = 39Ar(m)/40Ar(m) (col 96,97), Y = 36Ar(m)/40Ar(m) (col 94,95)
    x_inv = np.full(n, np.nan); x_inv_e = np.full(n, np.nan)
    y_inv = np.full(n, np.nan); y_inv_e = np.full(n, np.nan)
    # Normal isochron:  X = 39Ar(m)/36Ar(m) (col 92,93), Y = 40Ar(m)/36Ar(m) (col 90,91)
    x_nor = np.full(n, np.nan); x_nor_e = np.full(n, np.nan)
    y_nor = np.full(n, np.nan); y_nor_e = np.full(n, np.nan)
    for i in range(n):
        try:
            if len(rows[i]) > 97:
                y_inv[i] = float(rows[i][94]); y_inv_e[i] = float(rows[i][95])
                x_inv[i] = float(rows[i][96]); x_inv_e[i] = float(rows[i][97])
            if len(rows[i]) > 93:
                y_nor[i] = float(rows[i][90]); y_nor_e[i] = float(rows[i][91])
                x_nor[i] = float(rows[i][92]); x_nor_e[i] = float(rows[i][93])
        except Exception:
            pass

    spec_defs = {
        'age': dict(label='Age (Ma)',    y=y_age, yerr=y_err,    color=_st['age']),
        'atm': dict(label='%$^{40}$Ar*', y=y_atm, yerr=y_atm_err,color=_st['atm']),
        'cak': dict(label='Ca/K',        y=y_cak, yerr=y_cak_err,color=_st['cak']),
        'clk': dict(label='Cl/K',        y=y_clk, yerr=y_clk_err,color=_st['clk']),
    }

    keys = [k for k in panels if k in spec_defs or k in ('iso', 'isn')]
    if not keys:
        raise ValueError("No panels selected")

    def _draw_spec(ax, k):
        d = spec_defs[k]
        _draw_step_bars(ax, stepw, d['y'], d['yerr'], mask,
                        color=d['color'], edge=_st['edge'], lw=_st['lw'],
                        step_groups=step_groups, group_colors=group_colors)
        ax.set_ylabel(d['label'], fontsize=10)
        if _st.get('grid'):
            ax.grid(True, ls=':', lw=0.4, alpha=0.6)

    def _draw_iso(ax):
        '''Inverse isochron — matches standalone DFI: ellipses + fitted dashed line + intercept marker.'''
        m_arr = np.array(mask[:n], dtype=int) if hasattr(mask, '__len__') else np.ones(n, dtype=int)
        sel  = (m_arr != 0) & np.isfinite(x_inv) & np.isfinite(y_inv)
        if np.any(sel):
            # Error ellipses (1-sigma)
            t_th = np.linspace(0, 2*np.pi, 100)
            for i in np.where(sel)[0]:
                xs = x_inv[i] + x_inv_e[i] * np.cos(t_th)
                ys = y_inv[i] + y_inv_e[i] * np.sin(t_th)
                ax.plot(xs, ys, color='lightgray', linestyle='-', linewidth=0.7, zorder=2)
            # Per-point colour: group colour if assigned, else default iso_dot
            if step_groups and group_colors:
                for i in np.where(sel)[0]:
                    fc = _st['iso_dot']
                    if i in step_groups:
                        gi = step_groups[i] - 1
                        if 0 <= gi < len(group_colors):
                            fc = group_colors[gi]
                    ax.plot(x_inv[i], y_inv[i], 'o',
                            mfc=fc, mec=_st['edge'], ms=5, zorder=3)
            else:
                ax.plot(x_inv[sel], y_inv[sel], 'o',
                        mfc=_st['iso_dot'], mec=_st['edge'], ms=5, zorder=3)
            # Fitted dashed line + intercept marker (matches DFI standalone style)
            if show_overall_fit:
                try:
                    _xs = x_inv[sel].astype(float)
                    _ys = y_inv[sel].astype(float)
                    if len(_xs) >= 2:
                        _popt, _ = curve_fit(linear, _xs, _ys)
                        _x_ext = np.array([0.0, float(np.max(_xs)) * 1.05])
                        ax.plot(_x_ext, linear(_x_ext, *_popt),
                                linestyle='--', linewidth=1.2, color='r', zorder=4)
                        ax.plot(0, linear(0, *_popt), marker='o', ms=7,
                                mfc='red', mec='black', mew=0.8, zorder=6)
                except Exception:
                    pass
        excl = (m_arr == 0) & np.isfinite(x_inv) & np.isfinite(y_inv)
        if np.any(excl):
            ax.plot(x_inv[excl], y_inv[excl], 'rx', ms=8, mew=1.5, zorder=5)
        # === Per-group fitted lines + colored info boxes (matches standalone DFI) ===
        if show_group_fits and step_groups and group_colors:
            _grp_dfi = {}
            for _i in range(n):
                if (_i in step_groups and m_arr[_i] != 0
                        and np.isfinite(x_inv[_i]) and np.isfinite(y_inv[_i])):
                    _gn = step_groups[_i]
                    _grp_dfi.setdefault(_gn, ([], [], []))
                    _grp_dfi[_gn][0].append(x_inv[_i])
                    _grp_dfi[_gn][1].append(y_inv[_i])
                    _grp_dfi[_gn][2].append(y_inv_e[_i] if np.isfinite(y_inv_e[_i]) else 0.0)
            for _gn, (_gx, _gy, _gys) in sorted(_grp_dfi.items()):
                if len(_gx) < 2:
                    continue
                _gxa, _gya, _gysa = np.array(_gx), np.array(_gy), np.array(_gys)
                _N = len(_gxa)
                _gc = group_colors[_gn - 1] if _gn - 1 < len(group_colors) else 'black'
                try:
                    _gopt, _ = curve_fit(linear, _gxa, _gya)
                    _x_ext = np.array([0.0, float(np.max(_gxa)) * 1.1])
                    ax.plot(_x_ext, linear(_x_ext, *_gopt),
                            linestyle='-', linewidth=1.6, color=_gc,
                            zorder=5, label=f'Group {_gn}')
                    _ic = linear(0.0, *_gopt)
                    _slope = _gopt[0]
                    _atm_str = f'{1.0/_ic:.0f}' if _ic != 0 else '\u2014'
                    _age_str = ''
                    if (np.isfinite(_J_summary) and np.isfinite(_Lam_summary)
                            and _Lam_summary > 0 and _J_summary > 0
                            and _slope != 0 and _ic != 0):
                        _F = -_slope / _ic
                        if _F > 0:
                            _T = np.log(1.0 + _J_summary * _F) / _Lam_summary / 1e6
                            _age_str = f'\nT={_T:.1f} Ma'
                    _mswd = float('nan')
                    if _N >= 3 and np.all(np.isfinite(_gysa)) and np.all(_gysa > 0):
                        _resid = _gya - linear(_gxa, *_gopt)
                        _mswd = float(np.sum((_resid / _gysa) ** 2) / (_N - 2))
                    _mswd_str = f', MSWD={_mswd:.2f}' if _mswd == _mswd else ''
                    _ann_y = 0.98 - (_gn - 1) * 0.18
                    ax.annotate(
                        f'G{_gn} N={_N}{_mswd_str}{_age_str}\n\u2074\u2070/\u00b3\u2076={_atm_str}',
                        xy=(0.98, _ann_y), xycoords='axes fraction',
                        fontsize=6.5, color=_gc, fontweight='bold',
                        ha='right', va='top',
                        bbox=dict(boxstyle='round,pad=0.25', fc='gold',
                                  alpha=0.85, ec=_gc))
                except Exception:
                    pass
        ax.set_xlabel('$^{39}$Ar/$^{40}$Ar', fontsize=10)
        ax.set_ylabel('$^{36}$Ar/$^{40}$Ar', fontsize=10)
        if _st.get('grid'):
            ax.grid(True, ls=':', lw=0.4, alpha=0.6)

    def _draw_iso_n(ax):
        '''Normal isochron — matches standalone DFN: ellipses + fitted dashed line + intercept marker.'''
        m_arr = np.array(mask[:n], dtype=int) if hasattr(mask, '__len__') else np.ones(n, dtype=int)
        sel  = (m_arr != 0) & np.isfinite(x_nor) & np.isfinite(y_nor)
        if np.any(sel):
            t_th = np.linspace(0, 2*np.pi, 100)
            for i in np.where(sel)[0]:
                xs = x_nor[i] + x_nor_e[i] * np.cos(t_th)
                ys = y_nor[i] + y_nor_e[i] * np.sin(t_th)
                ax.plot(xs, ys, color='lightgray', linestyle='-', linewidth=0.7, zorder=2)
            if step_groups and group_colors:
                for i in np.where(sel)[0]:
                    fc = _st['iso_dot']
                    if i in step_groups:
                        gi = step_groups[i] - 1
                        if 0 <= gi < len(group_colors):
                            fc = group_colors[gi]
                    ax.plot(x_nor[i], y_nor[i], 'o',
                            mfc=fc, mec=_st['edge'], ms=5, zorder=3)
            else:
                ax.plot(x_nor[sel], y_nor[sel], 'o',
                        mfc=_st['iso_dot'], mec=_st['edge'], ms=5, zorder=3)
            if show_overall_fit:
                try:
                    _xs = x_nor[sel].astype(float)
                    _ys = y_nor[sel].astype(float)
                    if len(_xs) >= 2:
                        _popt, _ = curve_fit(linear, _xs, _ys)
                        _x_ext = np.array([0.0, float(np.max(_xs)) * 1.05])
                        ax.plot(_x_ext, linear(_x_ext, *_popt),
                                linestyle='--', linewidth=1.2, color='r', zorder=4)
                        ax.plot(0, linear(0, *_popt), marker='o', ms=7,
                                mfc='red', mec='black', mew=0.8, zorder=6)
                except Exception:
                    pass
        excl = (m_arr == 0) & np.isfinite(x_nor) & np.isfinite(y_nor)
        if np.any(excl):
            ax.plot(x_nor[excl], y_nor[excl], 'rx', ms=8, mew=1.5, zorder=5)
        # === Per-group fitted lines + info boxes (matches standalone DFN) ===
        if show_group_fits and step_groups and group_colors:
            _grp_dfn = {}
            for _i in range(n):
                if (_i in step_groups and m_arr[_i] != 0
                        and np.isfinite(x_nor[_i]) and np.isfinite(y_nor[_i])):
                    _gn = step_groups[_i]
                    _grp_dfn.setdefault(_gn, ([], [], []))
                    _grp_dfn[_gn][0].append(x_nor[_i])
                    _grp_dfn[_gn][1].append(y_nor[_i])
                    _grp_dfn[_gn][2].append(y_nor_e[_i] if np.isfinite(y_nor_e[_i]) else 0.0)
            for _gn, (_gx, _gy, _gys) in sorted(_grp_dfn.items()):
                if len(_gx) < 2:
                    continue
                _gxa, _gya, _gysa = np.array(_gx), np.array(_gy), np.array(_gys)
                _N = len(_gxa)
                _gc = group_colors[_gn - 1] if _gn - 1 < len(group_colors) else 'black'
                try:
                    _gopt, _ = curve_fit(linear, _gxa, _gya)
                    _x_ext = np.array([0.0, float(np.max(_gxa)) * 1.1])
                    ax.plot(_x_ext, linear(_x_ext, *_gopt),
                            linestyle='-', linewidth=1.6, color=_gc,
                            zorder=5, label=f'Group {_gn}')
                    _ic = linear(0.0, *_gopt)
                    _slope = _gopt[0]
                    _atm_str = f'{_ic:.0f}' if np.isfinite(_ic) else '\u2014'
                    _age_str = ''
                    if (np.isfinite(_J_summary) and np.isfinite(_Lam_summary)
                            and _Lam_summary > 0 and _J_summary > 0 and _slope > 0):
                        _T = np.log(1.0 + _J_summary * _slope) / _Lam_summary / 1e6
                        _age_str = f'\nT={_T:.1f} Ma'
                    if _N >= 3 and np.all(np.isfinite(_gysa)) and np.all(_gysa > 0):
                        _resid = _gya - linear(_gxa, *_gopt)
                        _mswd = float(np.sum((_resid / _gysa) ** 2) / (_N - 2))
                    _mswd_str = f', MSWD={_mswd:.2f}' if _mswd == _mswd else ''
                    _ann_y = 0.98 - (_gn - 1) * 0.18
                    ax.annotate(
                        f'G{_gn} N={_N}{_mswd_str}{_age_str}\n\u2074\u2070/\u00b3\u2076={_atm_str}',
                        xy=(0.98, _ann_y), xycoords='axes fraction',
                        fontsize=6.5, color=_gc, fontweight='bold',
                        ha='right', va='top',
                        bbox=dict(boxstyle='round,pad=0.25', fc='gold',
                                  alpha=0.85, ec=_gc))
                except Exception:
                    pass
        ax.set_xlabel('$^{39}$Ar/$^{36}$Ar', fontsize=10)
        ax.set_ylabel('$^{40}$Ar/$^{36}$Ar', fontsize=10)
        if _st.get('grid'):
            ax.grid(True, ls=':', lw=0.4, alpha=0.6)

    def _apply_panel_extras(ax, k):
        lim = panel_limits.get(k)
        if lim:
            xl, yl = lim
            if xl is not None: ax.set_xlim(xl)
            if yl is not None: ax.set_ylim(yl)
        ttl = panel_legends.get(k)
        if ttl:
            ax.set_title(ttl, fontsize=10)

    if layout == 'grid':
        ncols = 2
        nrows = (len(keys) + 1) // 2
        fig = plt.figure(figsize=(11, 3.2 * nrows + 0.6), dpi=150)
        gs  = gridspec.GridSpec(nrows, ncols, figure=fig,
                                hspace=0.35, wspace=0.25,
                                left=0.08, right=0.97, top=0.94, bottom=0.08)
        for idx, k in enumerate(keys):
            r, c = idx // ncols, idx % ncols
            if idx == len(keys) - 1 and len(keys) % 2 == 1:
                ax = fig.add_subplot(gs[r, :])
            else:
                ax = fig.add_subplot(gs[r, c])
            if k == 'iso':
                _draw_iso(ax)
            elif k == 'isn':
                _draw_iso_n(ax)
            else:
                _draw_spec(ax, k)
                ax.set_xlabel('Cumulative $^{39}$Ar (%)', fontsize=9)
            _apply_panel_extras(ax, k)
    else:
        spec_keys = [k for k in keys if k not in ('iso', 'isn')]
        iso_keys  = [k for k in keys if k in ('iso', 'isn')]   # preserve order
        nrows = len(spec_keys) + len(iso_keys)
        fig_h = 2.2 * len(spec_keys) + 4.5 * len(iso_keys)
        fig = plt.figure(figsize=(7.5, max(fig_h, 4.0)), dpi=150)
        h_ratios = [1.0] * len(spec_keys) + [2.0] * len(iso_keys)
        gs = gridspec.GridSpec(nrows, 1, figure=fig, height_ratios=h_ratios,
                               hspace=0.10, left=0.13, right=0.95,
                               top=0.95, bottom=0.07)
        share = None
        for r, k in enumerate(spec_keys):
            ax = fig.add_subplot(gs[r], sharex=share) if share is not None else fig.add_subplot(gs[r])
            share = share or ax
            _draw_spec(ax, k)
            is_last = (r == len(spec_keys) - 1) and (not iso_keys)
            if not is_last:
                ax.tick_params(labelbottom=False)
            else:
                ax.set_xlabel('Cumulative $^{39}$Ar Released (%)', fontsize=10)
            _apply_panel_extras(ax, k)
        for j, k in enumerate(iso_keys):
            ax_iv = fig.add_subplot(gs[len(spec_keys) + j])
            if k == 'isn':
                _draw_iso_n(ax_iv)
            else:
                _draw_iso(ax_iv)
            _apply_panel_extras(ax_iv, k)

    if legend_name:
        fig.suptitle(legend_name, fontsize=11)

    outdir = os.path.join(os.path.dirname(__file__), ".work")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "DFM.png")
    fig.savefig(out, dpi=300, facecolor=("white" if _st.get('classic') else "none"))
    plt.close('all')
    return out
