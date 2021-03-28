import math
import warnings
import numpy as np
import pandas as pd
import seaborn as sns
import scipy.stats as ss
import scipy.cluster.hierarchy as sch
import matplotlib.pyplot as plt
from collections import Counter
from ._private import (
    convert, remove_incomplete_samples, replace_nan_with_value
)

__all__ = [
    'associations',
    'cluster_correlations',
    'compute_associations',
    'conditional_entropy',
    'correlation_ratio',
    'cramers_v',
    'identify_columns_by_type',
    'identify_columns_with_na',
    'identify_nominal_columns',
    'identify_numeric_columns',
    'numerical_encoding',
    'theils_u'
]

_REPLACE = 'replace'
_DROP = 'drop'
_DROP_SAMPLES = 'drop_samples'
_DROP_FEATURES = 'drop_features'
_SKIP = 'skip'
_DEFAULT_REPLACE_VALUE = 0.0


def _inf_nan_str(x):
    if np.isnan(x):
        return 'NaN'
    elif abs(x) == np.inf:
        return 'inf'
    else:
        return ''


def identify_columns_with_na(dataset):
    dataset = convert(dataset, 'dataframe')
    na_count = [sum(dataset[cc].isnull()) for cc in dataset.columns]
    return pd.DataFrame({'column': dataset.columns, 'na_count': na_count}). \
        query('na_count > 0').sort_values('na_count', ascending=False)


def conditional_entropy(x,
                        y,
                        nan_strategy=_REPLACE,
                        nan_replace_value=_DEFAULT_REPLACE_VALUE,
                        log_base: float = math.e):
    if nan_strategy == _REPLACE:
        x, y = replace_nan_with_value(x, y, nan_replace_value)
    elif nan_strategy == _DROP:
        x, y = remove_incomplete_samples(x, y)
    y_counter = Counter(y)
    xy_counter = Counter(list(zip(x, y)))
    total_occurrences = sum(y_counter.values())
    entropy = 0.0
    for xy in xy_counter.keys():
        p_xy = xy_counter[xy] / total_occurrences
        p_y = y_counter[xy[1]] / total_occurrences
        entropy += p_xy * math.log(p_y / p_xy, log_base)
    return entropy


def cramers_v(x,
              y,
              bias_correction=True,
              nan_strategy=_REPLACE,
              nan_replace_value=_DEFAULT_REPLACE_VALUE):
    if nan_strategy == _REPLACE:
        x, y = replace_nan_with_value(x, y, nan_replace_value)
    elif nan_strategy == _DROP:
        x, y = remove_incomplete_samples(x, y)
    confusion_matrix = pd.crosstab(x, y)
    chi2 = ss.chi2_contingency(confusion_matrix)[0]
    n = confusion_matrix.sum().sum()
    phi2 = chi2 / n
    r, k = confusion_matrix.shape
    if bias_correction:
        phi2corr = max(0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
        rcorr = r - ((r - 1) ** 2) / (n - 1)
        kcorr = k - ((k - 1) ** 2) / (n - 1)
        if min((kcorr - 1), (rcorr - 1)) == 0:
            warnings.warn(
                "Unable to calculate Cramer's V using bias correction. Consider using bias_correction=False",
                RuntimeWarning)
            return np.nan
        else:
            return np.sqrt(phi2corr / min((kcorr - 1), (rcorr - 1)))
    else:
        return np.sqrt(phi2 / min(k - 1, r - 1))


def theils_u(x,
             y,
             nan_strategy=_REPLACE,
             nan_replace_value=_DEFAULT_REPLACE_VALUE):
    if nan_strategy == _REPLACE:
        x, y = replace_nan_with_value(x, y, nan_replace_value)
    elif nan_strategy == _DROP:
        x, y = remove_incomplete_samples(x, y)
    s_xy = conditional_entropy(x, y)
    x_counter = Counter(x)
    total_occurrences = sum(x_counter.values())
    p_x = list(map(lambda n: n / total_occurrences, x_counter.values()))
    s_x = ss.entropy(p_x)
    if s_x == 0:
        return 1
    else:
        return (s_x - s_xy) / s_x


def correlation_ratio(categories,
                      measurements,
                      nan_strategy=_REPLACE,
                      nan_replace_value=_DEFAULT_REPLACE_VALUE):
    if nan_strategy == _REPLACE:
        categories, measurements = replace_nan_with_value(
            categories, measurements, nan_replace_value)
    elif nan_strategy == _DROP:
        categories, measurements = remove_incomplete_samples(
            categories, measurements)
    categories = convert(categories, 'array')
    measurements = convert(measurements, 'array')
    fcat, _ = pd.factorize(categories)
    cat_num = np.max(fcat) + 1
    y_avg_array = np.zeros(cat_num)
    n_array = np.zeros(cat_num)
    for i in range(0, cat_num):
        cat_measures = measurements[np.argwhere(fcat == i).flatten()]
        n_array[i] = len(cat_measures)
        y_avg_array[i] = np.average(cat_measures)
    y_total_avg = np.sum(np.multiply(y_avg_array, n_array)) / np.sum(n_array)
    numerator = np.sum(
        np.multiply(n_array, np.power(np.subtract(y_avg_array, y_total_avg),
                                      2)))
    denominator = np.sum(np.power(np.subtract(measurements, y_total_avg), 2))
    if numerator == 0:
        eta = 0.0
    else:
        eta = np.sqrt(numerator / denominator)
    return eta


def identify_columns_by_type(dataset, include):
    dataset = convert(dataset, 'dataframe')
    columns = list(dataset.select_dtypes(include=include).columns)
    return columns


def identify_nominal_columns(dataset):
    return identify_columns_by_type(dataset, include=['object', 'category'])


def identify_numeric_columns(dataset):
    return identify_columns_by_type(dataset, include=['int64', 'float64'])


def _comp_assoc(dataset, nominal_columns, mark_columns, theil_u, clustering,
                bias_correction, nan_strategy, nan_replace_value):
    dataset = convert(dataset, 'dataframe')
    if nan_strategy == _REPLACE:
        dataset.fillna(nan_replace_value, inplace=True)
    elif nan_strategy == _DROP_SAMPLES:
        dataset.dropna(axis=0, inplace=True)
    elif nan_strategy == _DROP_FEATURES:
        dataset.dropna(axis=1, inplace=True)
    columns = dataset.columns
    if nominal_columns is None:
        nominal_columns = list()
    elif nominal_columns == 'all':
        nominal_columns = columns
    elif nominal_columns == 'auto':
        nominal_columns = identify_nominal_columns(dataset)

    corr = pd.DataFrame(index=columns, columns=columns)
    single_value_columns = []
    inf_nan = pd.DataFrame(data=np.zeros_like(corr),
                           columns=columns,
                           index=columns)
    for c in columns:
        if dataset[c].unique().size == 1:
            single_value_columns.append(c)
    for i in range(0, len(columns)):
        if columns[i] in single_value_columns:
            corr.loc[:, columns[i]] = 0.0
            corr.loc[columns[i], :] = 0.0
            continue
        for j in range(i, len(columns)):
            if columns[j] in single_value_columns:
                continue
            elif i == j:
                corr.loc[columns[i], columns[j]] = 1.0
            else:
                if columns[i] in nominal_columns:
                    if columns[j] in nominal_columns:
                        if theil_u:
                            ji = theils_u(
                                dataset[columns[i]],
                                dataset[columns[j]],
                                nan_strategy=_SKIP)
                            ij = theils_u(
                                dataset[columns[j]],
                                dataset[columns[i]],
                                nan_strategy=_SKIP)
                        else:
                            cell = cramers_v(dataset[columns[i]],
                                             dataset[columns[j]],
                                             bias_correction=bias_correction,
                                             nan_strategy=_SKIP)
                            ij = cell
                            ji = cell
                    else:
                        cell = correlation_ratio(dataset[columns[i]],
                                                 dataset[columns[j]],
                                                 nan_strategy=_SKIP)
                        ij = cell
                        ji = cell
                else:
                    if columns[j] in nominal_columns:
                        cell = correlation_ratio(dataset[columns[j]],
                                                 dataset[columns[i]],
                                                 nan_strategy=_SKIP)
                        ij = cell
                        ji = cell
                    else:
                        cell, _ = ss.pearsonr(dataset[columns[i]],
                                              dataset[columns[j]])
                        ij = cell
                        ji = cell
                corr.loc[columns[i], columns[j]] = ij if not np.isnan(ij) and abs(ij) < np.inf else 0.0
                corr.loc[columns[j], columns[i]] = ji if not np.isnan(ji) and abs(ji) < np.inf else 0.0
                inf_nan.loc[columns[i], columns[j]] = _inf_nan_str(ij)
                inf_nan.loc[columns[j], columns[i]] = _inf_nan_str(ji)
    corr.fillna(value=np.nan, inplace=True)
    if mark_columns:
        marked_columns = [
            '{} (nom)'.format(col)
            if col in nominal_columns else '{} (con)'.format(col)
            for col in columns
        ]
        corr.columns = marked_columns
        corr.index = marked_columns
        inf_nan.columns = marked_columns
        inf_nan.index = marked_columns
    if clustering:
        corr, _ = cluster_correlations(corr)
        columns = corr.columns
    return corr, columns, nominal_columns, inf_nan, single_value_columns


def compute_associations(dataset,
                         nominal_columns='auto',
                         mark_columns=False,
                         theil_u=False,
                         clustering=False,
                         bias_correction=True,
                         nan_strategy=_REPLACE,
                         nan_replace_value=_DEFAULT_REPLACE_VALUE,
                         ):
    corr, _, _, _, _ = _comp_assoc(dataset, nominal_columns, mark_columns, theil_u, clustering,
                                   bias_correction, nan_strategy, nan_replace_value)
    return corr


def associations(dataset,
                 dirFinal,
                 nominal_columns='auto',
                 mark_columns=False,
                 theil_u=False,
                 plot=True,
                 clustering=False,
                 bias_correction=True,
                 nan_strategy=_REPLACE,
                 nan_replace_value=_DEFAULT_REPLACE_VALUE,
                 ax=None,
                 figsize=(30,30),
                 annot=True,
                 fmt='.2f',
                 cmap=None,
                 sv_color='silver',
                 cbar=True
                 ):

    corr, columns, nominal_columns, inf_nan, single_value_columns = _comp_assoc(dataset, nominal_columns, mark_columns,
                                                                                theil_u, clustering, bias_correction,
                                                                                nan_strategy, nan_replace_value)
    if ax is None:
        plt.figure(figsize=figsize)
    if inf_nan.any(axis=None):
        inf_nan_mask = np.vectorize(lambda x: not bool(x))(inf_nan.values)
        ax = sns.heatmap(inf_nan_mask,
                         cmap=['white'],
                         annot=inf_nan if annot else None,
                         fmt='',
                         center=0,
                         square=True,
                         ax=ax,
                         mask=inf_nan_mask,
                         cbar=False)
    else:
        inf_nan_mask = np.ones_like(corr)
    if len(single_value_columns) > 0:
        sv = pd.DataFrame(data=np.zeros_like(corr),
                          columns=columns,
                          index=columns)
        for c in single_value_columns:
            sv.loc[:, c] = ' '
            sv.loc[c, :] = ' '
            sv.loc[c, c] = 'SV'
        sv_mask = np.vectorize(lambda x: not bool(x))(sv.values)
        ax = sns.heatmap(sv_mask,
                         cmap=[sv_color],
                         annot=sv if annot else None,
                         fmt='',
                         center=0,
                         square=True,
                         ax=ax,
                         mask=sv_mask,
                         cbar=False)
    else:
        sv_mask = np.ones_like(corr)
    mask = np.vectorize(lambda x: not bool(x))(inf_nan_mask) + np.vectorize(lambda x: not bool(x))(sv_mask)
    ax = sns.heatmap(corr,
                     cmap=cmap,
                     annot=annot,
                     fmt=fmt,
                     center=0,
                     vmax=1.0,
                     vmin=-1.0 if len(columns) - len(nominal_columns) >= 2 else 0.0,
                     square=True,
                     mask=mask,
                     ax=ax,
                     cbar=cbar)
    if plot:
        plt.show()
    
    plt.savefig(dirFinal+'corr_plot.png')
    plt.savefig(dirFinal+'corr_plot.pdf')
    
    return {'corr': corr,
            'ax': ax}


def numerical_encoding(dataset,
                       nominal_columns='auto',
                       drop_single_label=False,
                       drop_fact_dict=True,
                       nan_strategy=_REPLACE,
                       nan_replace_value=_DEFAULT_REPLACE_VALUE):
    dataset = convert(dataset, 'dataframe')
    if nan_strategy == _REPLACE:
        dataset.fillna(nan_replace_value, inplace=True)
    elif nan_strategy == _DROP_SAMPLES:
        dataset.dropna(axis=0, inplace=True)
    elif nan_strategy == _DROP_FEATURES:
        dataset.dropna(axis=1, inplace=True)
    if nominal_columns is None:
        return dataset
    elif nominal_columns == 'all':
        nominal_columns = dataset.columns
    elif nominal_columns == 'auto':
        nominal_columns = identify_nominal_columns(dataset)
    converted_dataset = pd.DataFrame()
    binary_columns_dict = dict()
    for col in dataset.columns:
        if col not in nominal_columns:
            converted_dataset.loc[:, col] = dataset[col]
        else:
            unique_values = pd.unique(dataset[col])
            if len(unique_values) == 1 and not drop_single_label:
                converted_dataset.loc[:, col] = 0
            elif len(unique_values) == 2:
                converted_dataset.loc[:, col], binary_columns_dict[
                    col] = pd.factorize(dataset[col])
            else:
                dummies = pd.get_dummies(dataset[col], prefix=col)
                converted_dataset = pd.concat([converted_dataset, dummies],
                                              axis=1)
    if drop_fact_dict:
        return converted_dataset
    else:
        return converted_dataset, binary_columns_dict


def cluster_correlations(corr_mat, indices=None):
    if indices is None:
        X = corr_mat.values
        d = sch.distance.pdist(X)
        L = sch.linkage(d, method='complete')
        indices = sch.fcluster(L, 0.5 * d.max(), 'distance')
    columns = [corr_mat.columns.tolist()[i]
               for i in list((np.argsort(indices)))]
    corr_mat = corr_mat.reindex(columns=columns).reindex(index=columns)
    return corr_mat, indices
