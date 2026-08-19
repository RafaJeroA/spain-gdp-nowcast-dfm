function result = estimate_dfm(y, start_theta, options)
%ESTIMATE_DFM Estimate the 29-state DFM by maximum likelihood.

if nargin < 2 || isempty(start_theta)
    n_series = size(y, 2);
    n_ar_processes = 8;  % common factor, GDP idio, six monthly idios
    start_loadings = 0.50 * ones(n_series, 1);
    start_ar = repmat([0.50; 0.20], n_ar_processes, 1);
    start_sigmas = 0.90 * ones(n_series, 1);
    start_theta = [start_loadings; start_ar; start_sigmas];
end

if nargin < 3 || isempty(options)
    options = optimset('Display', 'off', 'TolFun', 1e-8, 'MaxFunEvals', 7000);
end

[z, means, stdevs] = standardize_observed(y);
objective = @(theta) kalman_objective(theta, z);
[theta, fval, exitflag, output] = fminunc(objective, start_theta, options);
[loglik, states, covariances] = kalman_filter(theta, z);
[Q, H, F] = state_space_matrices(theta);

ar_pairs = reshape(theta(8:23), 2, []).';
max_ar_eigenvalue = 0;
for j = 1:size(ar_pairs, 1)
    companion = [ar_pairs(j, 1), ar_pairs(j, 2); 1, 0];
    max_ar_eigenvalue = max(max_ar_eigenvalue, max(abs(eig(companion))));
end
if max_ar_eigenvalue >= 1
    warning('At least one fitted AR(2) block is not stationary (max eigenvalue %.3f).', ...
        max_ar_eigenvalue);
end

result.theta = theta;
result.fval = fval;
result.exitflag = exitflag;
result.output = output;
result.loglik = loglik;
result.states = states;
result.covariances = covariances;
result.means = means;
result.stdevs = stdevs;
result.Q = Q;
result.H = H;
result.F = F;
result.max_ar_eigenvalue = max_ar_eigenvalue;
end
