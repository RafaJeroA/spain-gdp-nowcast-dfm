function objective = kalman_objective(theta, y)
%KALMAN_OBJECTIVE Negative Kalman log-likelihood.

try
    loglik = kalman_filter(theta, y);
catch
    objective = 1e10;
    return
end

burn_in = min(20, numel(loglik));
objective = -sum(loglik(burn_in:end));
if ~isfinite(objective)
    objective = 1e10;
end
end
