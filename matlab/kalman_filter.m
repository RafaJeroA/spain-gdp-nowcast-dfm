function [loglik, states, covariances] = kalman_filter(theta, y)
%KALMAN_FILTER Filter the mixed-frequency panel using observed rows only.
%
% Missing observations are omitted from that month's measurement update.
% This replaces the random-fill device used in the original class version
% while leaving the 29-state model and measurement equations unchanged.

[Q, H, F] = state_space_matrices(theta);
[n_obs, ~] = size(y);
n_states = size(F, 1);

state = zeros(n_states, 1);
P = eye(n_states);
I = eye(n_states);

loglik = zeros(n_obs, 1);
states = zeros(n_obs, n_states);
covariances = zeros(n_states, n_states, n_obs);

for t = 1:n_obs
    state_pred = F * state;
    P_pred = F * P * F' + Q;
    P_pred = (P_pred + P_pred') / 2;

    observed = isfinite(y(t, :));
    if any(observed)
        H_t = H(observed, :);
        innovation = y(t, observed)' - H_t * state_pred;
        S = H_t * P_pred * H_t';
        S = (S + S') / 2;

        % A tiny numerical jitter is used only if round-off prevents Cholesky.
        [L, flag] = chol(S, 'lower');
        if flag ~= 0
            S = S + 1e-9 * eye(size(S));
            [L, flag] = chol(S, 'lower');
        end
        if flag ~= 0
            error('Innovation covariance is not positive definite at t=%d.', t);
        end

        logdetS = 2 * sum(log(diag(L)));
        solved = L' \ (L \ innovation);
        loglik(t) = -0.5 * (numel(innovation) * log(2*pi) + logdetS + innovation' * solved);

        K = (P_pred * H_t') / S;
        state = state_pred + K * innovation;
        P = (I - K * H_t) * P_pred;
        P = (P + P') / 2;
    else
        state = state_pred;
        P = P_pred;
    end

    states(t, :) = state';
    covariances(:, :, t) = P;
end
end
