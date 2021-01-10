import numpy as np
import pandas as pd
import os


# Define metrics

def coverage(y_true, y_pred):
    """

    Args:
        y_true: Time series of observed forecast errors
        y_pred: Time series of corresponding conditional quantile estimates from machine learning model

    Returns:
        Fraction of observed forecast errors that fall below / are "covered" by quantile estimates

    """
    return np.mean(y_true <= y_pred)


def requirement(y_true, y_pred):
    """

    Args:
        y_true: Time series of observed forecast errors
        y_pred: Time series of corresponding conditional quantile estimates from machine learning model

    Returns:
        Average reserve level/requirement, which corresponds to the average of the quantile estimates

    """
    return np.mean(y_pred)


def exceeding(y_true, y_pred):
    """

    Args:
        y_true: Time series of observed forecast errors
        y_pred: Time series of corresponding conditional quantile estimates from machine learning model

    Returns:
        Average excess of observed forecast errors above the quantile estimates when observed forecast errors exceed
            corresponding quantile estimates

    """
    return np.mean((y_true - y_pred)[y_true > y_pred])


def closeness(y_true, y_pred):
    """

    Args:
        y_true: Time series of observed forecast errors
        y_pred: Time series of corresponding conditional quantile estimates from machine learning model

    Returns:
        Average (absolute) distance between observed forecast errors and quantile estimates; equivalent to mean average
            error (MAE) between observed forecast errors and quantile estimates

    """
    return np.mean(np.abs(y_true - y_pred))


def max_exceeding(y_true, y_pred):
    """

    Args:
        y_true: Time series of observed forecast errors
        y_pred: Time series of corresponding conditional quantile estimates from machine learning model

    Returns:
        Maximum excess of observed forecast errors above corresponding quantile estimates

    """
    return np.max(y_true - y_pred)


def reserve_ramp_rate(y_true, y_pred):
    '''

    Args:
        y_true: Time series of observed forecast errors
        y_pred: Time series of corresponding conditional quantile estimates from machine learning model

    Returns:
        Average ramp rate of reserve level/requirement (average absolute rate of change)

    '''
    return np.mean(np.abs(y_pred.values[1:] - y_pred.values[:-1]) / (
                (y_pred.index[1:] - y_pred.index[:-1]).astype(int) / (1e9 * 3600)))


def pinball_loss(y_true, y_pred, tau=0.975):
    """

    Args:
        y_true: Time seriers of observed forecast errors
        y_pred: Time series of corresponding conditional quantile estimates from machine learning model
        tau: Target percentile for quantile estimates (needed within calculation); default = 0.975

    Returns:
        Average pinball loss of input data; similar to "closeness" metric, but samples are re-weighted so that the
            metric is minimized for "optimal" or "true" quantile estimation models

    """
    return np.mean(np.max(np.array([(1 - tau) * (y_pred - y_true), tau * (y_true - y_pred)]), axis=0))


# Define function to compute/writeout metrics

def compute_metrics_for_specified_tau(output_trainval, pred_trainval, df=None, tau=0.975,
                                      filename=None, metrics=[coverage,
                                                              requirement,
                                                              exceeding,
                                                              closeness,
                                                              max_exceeding,
                                                              reserve_ramp_rate,
                                                              pinball_loss]):
    """

    Description:
        Iteratively computes metrics for input data and returns metrics in a pandas dataframe

    Args:
        output_trainval: Dataframe of observed forecast errors
        pred_trainval: Dataframe of corresponding conditional quantile estimates from machine learning model for
            multiple CV folds
        df: Existing dataframe containing metrics (e.g. for another tau-level); default = None
        tau: Target percentile for predictions (also an input for pinball loss metric); default = 0.975
        filename: Path to file where metrics will be saved if filename specified; default = None
        metrics: List of metrics to compute for input data

    Returns:
        df: Dataframe containing metrics for current value of tau (and with metrics for other values of tau if existing
            dataframe was passed to function

    Example usage:

        # Get metrics dataframe for target percentile of 97.5%
        df_metrics = compute_metrics(output_trainval, pred_trainval)

        # Get metrics dataframe for target percentiles of 95% and 97.5% by passing previously computed dataframe
        df_metrics = compute_metrics(output_trainval, pred_trainval, tau = 0.95, df = df_metrics)

        # Save metrics dataframe to "file.csv"
        compute_metrics(output_trainval, pred_trainval, filename = 'file.csv')

    """

    pinball_loss.__defaults__ = (tau,)
    # Set pinball risk default tau-level to input tau (default will remain tau = 0.975 if no value is specified)
    CV_folds = np.arange(10)  # Define array of CV fold IDs

    if df is None:
        df = pd.DataFrame()  # Create new dataframe if no existing dataframe is given
        df['metrics'] = [metric.__name__ for metric in metrics]
        df.set_index('metrics', inplace=True)  # Set index to list of metrics
        df.index.name = None

    y_true = output_trainval  # Define y_true
    for j, CV in enumerate(CV_folds):
        y_pred = pred_trainval[(tau, CV)]  # Define y_pred (from tau, CV fold ID)
        df[(tau, CV)] = ""  # Create empty column to hold metrics
        for metric in metrics:
            df[(tau, CV)][metric.__name__] = metric(y_true, y_pred)  # Compute metric

    df = df.T.set_index(
        pd.MultiIndex.from_tuples(df.T.index, names=('Quantiles', 'Fold ID'))).T  # Reformat to have multi-level columns

    if filename is not None:
        df.to_csv(filename)  # Write to CSV file

    return df


def compute_metrics_for_all_taus(output_trainval, pred_trainval, avg_across_folds=True):
    """
    :param output_trainval:Dataframe of observed forecast errors
    :param pred_trainval: Dataframe of corresponding conditional quantile estimates from machine learning model for
            multiple CV folds and multiple tau. The columns are two leveled, with the sequence being (tau, CV)
    :param avg_across_folds: a boolean determining whether to return the metrics for each fold or the average
    :return: Dataframe containing metrics for all values of tau present in the pred_trainval
    """

    metrics_value_df = None

    for tau in pred_trainval.columns.levels[0]:
        metrics_value_df = compute_metrics_for_specified_tau(output_trainval, pred_trainval,
                                                             df=metrics_value_df, tau=tau)

    if avg_across_folds:
        metrics_value_df = metrics_value_df.astype('float').mean(axis=1, level=0)

    return metrics_value_df


def n_crossings(pred_trainval):
    """

    Computes number of quantile crossings within CV folds for various target percentile pairs

    Args:
        pred_trainval: Dataframe containing quantile estimates for each CV fold and target percentile

    Returns:
        Dataframe containing number of quantile crossings for each pair of target percentiles within each CV fold
            (only for valid pairs of "lower" and "upper" target percentiles)
    """

    columns = pred_trainval.columns # Get columns
    tau_arr = np.sort(np.unique(np.array([c[0] for c in columns])))  # Tau values need to be sorted
    CV_arr = np.sort(np.unique(np.array([c[1] for c in columns])))

    crossings = {} # Define dictionary to store crossings

    for CV in CV_arr:
        # Look for quantile crossings only in sets of predictions from models trained on same CV fold
        crossings[CV] = {}
        for i, t1 in enumerate(tau_arr):
            for j, t2 in enumerate(tau_arr):
                if t1 < t2: # Only evaluate number of quantile crossings on valid lower/upper target percentile pairs
                    crossings[CV][(t1, t2)] = sum(
                        pred_trainval[t1, CV] > pred_trainval[t2, CV])  # Record number of quantile crossings

    df = pd.DataFrame(crossings)
    df.columns.name = 'CV Fold ID'
    df.index.rename(['Lower Quantile', 'Upper Quantile'], inplace=True)
    return df


if __name__ == "__main__":
    CAISO_data = pd.read_csv(os.path.join('CAISO Metrics', 'CAISO_measurements.csv'), index_col='Unnamed: 0')

    print('Measurements reported by CAISO for Histogram method:\n')

    print('Coverage: {}%'.format(100 * CAISO_data['Coverage']['Histogram']))
    print('Requirement: {} MW'.format(CAISO_data['Requirement']['Histogram']))
    print('Closeness: {} MW'.format(CAISO_data['Closeness']['Histogram']))
    print('Exceeding: {} MW'.format(CAISO_data['Exceeding']['Histogram']))

    print('\nMeasurements reported by CAISO for Quantile Regression method:\n')

    print('Coverage: {}%'.format(100 * CAISO_data['Coverage']['Quantile Regression']))
    print('Requirement: {} MW'.format(CAISO_data['Requirement']['Quantile Regression']))
    print('Closeness: {} MW'.format(CAISO_data['Closeness']['Quantile Regression']))
    print('Exceeding: {} MW'.format(CAISO_data['Exceeding']['Quantile Regression']))

    print('\nRESCUE performance metrics:\n')

    output_trainval = pd.read_pickle(
        'C:\\Users\\charles.gulian\\PycharmProjects\\RESCUE\\data\\rescue_v1_2\\output_trainval.pkl')
    pred_trainval1 = pd.read_pickle(
        'C:\\Users\\charles.gulian\\PycharmProjects\\RESCUE\\output\\rescue_v1_1\\pred_trainval.pkl')

    df = compute_metrics_for_specified_tau(output_trainval, pred_trainval1)

    print('Coverage: {:.2f}%'.format(100 * df.loc['coverage'].mean()))
    print('Requirement: {:.2f} MW'.format(df.loc['requirement'].mean()))
    print('Closeness: {:.2f} MW'.format(df.loc['closeness'].mean()))
    print('Exceeding: {:.2f} MW'.format(df.loc['exceeding'].mean()))
    print('Max. Exceeding: {:.2f} MW'.format(df.loc['max_exceeding'].mean()))
    print('Mean Reserve Ramp Rate: {:.2f} MW/hr'.format(df.loc['reserve_ramp_rate'].mean()))
    print('Pinball Risk: {:.2f} MW'.format(df.loc['pinball_loss'].mean()))

    print('\nMetrics dataframe:\n')
    print(df)
