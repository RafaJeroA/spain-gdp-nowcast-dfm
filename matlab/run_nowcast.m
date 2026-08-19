%% Spain GDP nowcast: mixed-frequency dynamic factor model

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
y = table2array(T(:, series_names));
y(y == 99999) = NaN;

options = optimset('Display', 'iter', 'TolFun', 1e-8, 'MaxFunEvals', 7000);
fit = estimate_dfm(y, [], options);
if fit.exitflag <= 0
    warning('fminunc did not report normal convergence (exitflag %d).', fit.exitflag);
end

%% Current two-quarter forecast
valid_gdp = isfinite(y(:, 1));
last_gdp_idx = find(valid_gdp, 1, 'last');
last_gdp_date = dates(last_gdp_idx);
forecast_dates = last_gdp_date + calmonths([3; 6]);

last_state = fit.states(end, :)';
last_covariance = fit.covariances(:, :, end);
forecast_values = zeros(2, 1);
forecast_se = zeros(2, 1);

% Gaussian intervals conditional on the fitted parameters. The state
% covariance is propagated with the same transition matrix and shock
% covariance used by the Kalman filter; parameter uncertainty is not added.
z65 = 0.9345892910734798;
z95 = 1.959963984540054;

for k = 1:2
    state = last_state;
    P = last_covariance;
    months_ahead = (year(forecast_dates(k)) - year(dates(end))) * 12 ...
        + month(forecast_dates(k)) - month(dates(end));

    for h = 1:months_ahead
        state = fit.F * state;
        P = fit.F * P * fit.F' + fit.Q;
        P = (P + P') / 2;
    end

    gdp_std_forecast = fit.H(1, :) * state;
    gdp_std_variance = fit.H(1, :) * P * fit.H(1, :)';
    forecast_values(k) = gdp_std_forecast * fit.stdevs(1) + fit.means(1);
    forecast_se(k) = sqrt(max(gdp_std_variance, 0)) * fit.stdevs(1);
end

lower_65 = forecast_values - z65 * forecast_se;
upper_65 = forecast_values + z65 * forecast_se;
lower_95 = forecast_values - z95 * forecast_se;
upper_95 = forecast_values + z95 * forecast_se;

information_set_through = repmat(string(datestr(dates(end), 'yyyy-mm')), 2, 1);

forecast_table = table(forecast_dates(:), forecast_values(:), forecast_se(:), ...
    lower_65(:), upper_65(:), lower_95(:), upper_95(:), ...
    information_set_through, ...
    'VariableNames', {'date', 'gdp_forecast_qoq', 'forecast_se', ...
    'lower_65', 'upper_65', 'lower_95', 'upper_95', ...
    'information_set_through'});
writetable(forecast_table, fullfile(output_dir, 'current_forecasts.csv'));
disp(forecast_table);

%% Factor diagnostics
factor = fit.states(:, 1);
factor_quarterly = factor(valid_gdp);
gdp_observed = y(valid_gdp, 1);
factor_z = local_zscore(factor_quarterly);
gdp_z = local_zscore(gdp_observed);
C = corrcoef(factor_z, gdp_z);
corr_factor_gdp = C(1, 2);
fprintf('In-sample factor/GDP correlation: %.3f\n', corr_factor_gdp);
fprintf('Treat this as a descriptive diagnostic; GDP enters the state-space fit.\n');

figure('Visible', 'off');
plot(dates, factor, 'LineWidth', 1.2);
grid on;
title('Estimated Spanish real-activity factor');
xlabel('Date');
ylabel('Factor');
saveas(gcf, fullfile(output_dir, 'figure_factor.png'));
close(gcf);

figure('Visible', 'off');
plot(dates(valid_gdp), factor_z, 'LineWidth', 1.2);
hold on;
plot(dates(valid_gdp), gdp_z, '--', 'LineWidth', 1.2);
grid on;
title('Estimated factor vs observed Spanish GDP growth');
xlabel('Date');
ylabel('Standardised values');
legend('Estimated factor, quarterly', 'Observed GDP q/q growth', 'Location', 'best');
saveas(gcf, fullfile(output_dir, 'figure_factor_vs_gdp_quarterly.png'));
close(gcf);

factor_monthly_z = (factor - mean(factor_quarterly)) ./ std(factor_quarterly);
figure('Visible', 'off');
plot(dates, factor_monthly_z, 'LineWidth', 1.2);
hold on;
plot(dates(valid_gdp), gdp_z, 'o--', 'LineWidth', 1.2, 'MarkerSize', 4);
grid on;
title('Monthly estimated factor vs observed Spanish GDP growth');
xlabel('Date');
ylabel('Standardised values');
legend('Estimated factor, monthly', 'Observed GDP q/q growth, quarterly', 'Location', 'best');
saveas(gcf, fullfile(output_dir, 'figure_factor_vs_gdp_monthly.png'));
close(gcf);

fprintf('Outputs written to %s\n', output_dir);

function z = local_zscore(x)
    x = x(:);
    z = (x - mean(x)) ./ std(x);
end
