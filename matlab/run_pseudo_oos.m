%% Expanding-window pseudo-out-of-sample evaluation
%
% Each target quarter is nowcast using monthly information through the second
% month of that quarter. GDP for the target quarter is therefore not available
% to the model. The model and standardisation are re-estimated in every fold.

clear;
clc;
rng(123);

repo_root = fileparts(fileparts(mfilename('fullpath')));
addpath(fullfile(repo_root, 'matlab'));
input_file = fullfile(repo_root, 'data', 'spain_data.xlsx');
output_dir = fullfile(repo_root, 'outputs');
if ~exist(output_dir, 'dir')
    mkdir(output_dir);
end

T = readtable(input_file, 'Sheet', 'data');
dates = T.date;
series_names = {'gdp_qoq', 'ipi', 'affiliation', 'retail_sales', ...
    'imports', 'tourism_overnights', 'esi'};
y_full = table2array(T(:, series_names));
y_full(y_full == 99999) = NaN;

is_quarter_end = ismember(month(dates), [3, 6, 9, 12]);
target_rows = find(is_quarter_end & isfinite(y_full(:, 1)) & dates >= datetime(2015, 3, 1));

options = optimset('Display', 'off', 'TolFun', 1e-8, 'MaxFunEvals', 7000);
previous_theta = [];
records = [];

for i = 1:numel(target_rows)
    target_idx = target_rows(i);
    target_date = dates(target_idx);
    cutoff_date = target_date - calmonths(1);
    train_mask = dates <= cutoff_date;
    y_train = y_full(train_mask, :);

    target_label = sprintf('%dQ%d', year(target_date), ceil(month(target_date) / 3));
    fprintf('Estimating %s using information through %s...\n', ...
        target_label, datestr(cutoff_date, 'yyyy-mm'));

    try
        fit = estimate_dfm(y_train, previous_theta, options);
    catch ME
        warning('Skipping %s: %s', datestr(target_date), ME.message);
        continue
    end
    if fit.exitflag <= 0
        warning('Fold %s has fminunc exitflag %d.', datestr(target_date), fit.exitflag);
    end
    previous_theta = fit.theta;

    state = fit.F * fit.states(end, :)';
    dfm_forecast = (fit.H(1, :) * state) * fit.stdevs(1) + fit.means(1);
    actual = y_full(target_idx, 1);

    previous_date = target_date - calmonths(3);
    previous_idx = find(dates == previous_date, 1);
    persistence = NaN;
    if ~isempty(previous_idx) && isfinite(y_full(previous_idx, 1))
        persistence = y_full(previous_idx, 1);
    end

    historical_gdp = y_full(train_mask, 1);
    historical_gdp = historical_gdp(isfinite(historical_gdp));
    historical_mean = mean(historical_gdp);
    ar1_forecast = local_ar1_forecast(dates(train_mask), y_full(train_mask, 1), previous_date);

    records = [records; ... %#ok<AGROW>
        datenum(target_date), datenum(cutoff_date), actual, dfm_forecast, ...
        persistence, ar1_forecast, historical_mean, fit.exitflag];
end

predictions = array2table(records, 'VariableNames', ...
    {'target_datenum', 'cutoff_datenum', 'actual', 'dfm', 'persistence', ...
     'ar1', 'historical_mean', 'exitflag'});
predictions.target_date = datetime(predictions.target_datenum, 'ConvertFrom', 'datenum');
predictions.cutoff_date = datetime(predictions.cutoff_datenum, 'ConvertFrom', 'datenum');
predictions = movevars(predictions, {'target_date', 'cutoff_date'}, 'Before', 1);
predictions.target_datenum = [];
predictions.cutoff_datenum = [];

% Keep the 2021Q1 DFM forecast in the detailed output, but compare models on
% the same set of quarters. Persistence and AR(1) are unavailable for 2021Q1
% because 2020Q4 GDP is masked by the assignment specification.
common_sample = isfinite(predictions.actual) & isfinite(predictions.dfm) ...
    & isfinite(predictions.persistence) & isfinite(predictions.ar1);
predictions.common_sample = common_sample;

writetable(predictions, fullfile(output_dir, 'pseudo_oos_predictions.csv'));

models = {'dfm', 'persistence', 'ar1', 'historical_mean'};
metrics = table('Size', [numel(models), 5], ...
    'VariableTypes', {'string', 'double', 'double', 'double', 'double'}, ...
    'VariableNames', {'model', 'n', 'rmse', 'mae', 'correlation'});

for j = 1:numel(models)
    name = models{j};
    pred = predictions.(name);
    valid = common_sample & isfinite(pred);
    errors = pred(valid) - predictions.actual(valid);
    metrics.model(j) = string(name);
    metrics.n(j) = sum(valid);
    metrics.rmse(j) = sqrt(mean(errors.^2));
    metrics.mae(j) = mean(abs(errors));
    if sum(valid) >= 3
        C = corrcoef(pred(valid), predictions.actual(valid));
        metrics.correlation(j) = C(1, 2);
    else
        metrics.correlation(j) = NaN;
    end
end

writetable(metrics, fullfile(output_dir, 'pseudo_oos_metrics.csv'));
fprintf('Common evaluation sample: %d quarters.\n', sum(common_sample));
disp(metrics);

% Plot on a complete quarterly date grid so the masked 2020 observations
% appear as a real gap rather than a line joining 2019Q4 directly to 2021Q1.
plot_dates = (predictions.target_date(1):calmonths(3):predictions.target_date(end))';
actual_plot = nan(size(plot_dates));
dfm_plot = nan(size(plot_dates));
persistence_plot = nan(size(plot_dates));
[is_present, locations] = ismember(predictions.target_date, plot_dates);
actual_plot(locations(is_present)) = predictions.actual(is_present);
dfm_plot(locations(is_present)) = predictions.dfm(is_present);
persistence_plot(locations(is_present)) = predictions.persistence(is_present);

figure('Visible', 'off');
plot(plot_dates, actual_plot, 'k-', 'LineWidth', 1.2);
hold on;
plot(plot_dates, dfm_plot, 'LineWidth', 1.2);
plot(plot_dates, persistence_plot, '--', 'LineWidth', 1.0);
grid on;
title({'Pseudo-OOS Spanish GDP nowcasts', '2020 masked by assignment specification'});
xlabel('Target quarter');
ylabel('GDP growth q/q (%)');
legend('Actual', 'DFM nowcast', 'Persistence', 'Location', 'best');
saveas(gcf, fullfile(output_dir, 'figure_pseudo_oos.png'));
close(gcf);

fprintf('Pseudo-OOS outputs written to %s\n', output_dir);

function forecast = local_ar1_forecast(dates, gdp, previous_date)
    forecast = NaN;
    previous_idx = find(dates == previous_date, 1);
    if isempty(previous_idx) || ~isfinite(gdp(previous_idx))
        return
    end

    valid = isfinite(gdp);
    quarterly_dates = dates(valid);
    quarterly_gdp = gdp(valid);
    lag_values = [];
    current_values = [];
    for t = 2:numel(quarterly_dates)
        month_gap = (year(quarterly_dates(t)) - year(quarterly_dates(t-1))) * 12 ...
            + month(quarterly_dates(t)) - month(quarterly_dates(t-1));
        if month_gap == 3
            lag_values(end + 1, 1) = quarterly_gdp(t-1); %#ok<AGROW>
            current_values(end + 1, 1) = quarterly_gdp(t); %#ok<AGROW>
        end
    end
    if numel(current_values) < 8
        return
    end

    X = [ones(size(lag_values)), lag_values];
    beta = X \ current_values;
    forecast = [1, gdp(previous_idx)] * beta;
end
