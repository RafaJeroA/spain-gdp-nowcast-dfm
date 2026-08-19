function [Q, H, F] = state_space_matrices(theta)
%STATE_SPACE_MATRICES Build the 29-state mixed-frequency DFM matrices.
%
% State layout
%   1:12   common factor and 11 monthly lags
%   13:17  GDP idiosyncratic component and 4 lags
%   18:19  IPI idiosyncratic AR(2)
%   20:21  affiliation idiosyncratic AR(2)
%   22:23  retail-sales idiosyncratic AR(2)
%   24:25  imports idiosyncratic AR(2)
%   26:27  tourism idiosyncratic AR(2)
%   28:29  ESI idiosyncratic AR(2)

n_states = 29;
quarterly_weights = [1/3, 2/3, 1, 2/3, 1/3];
loadings = theta(1:7);
ar_pairs = reshape(theta(8:23), 2, []).';
shock_scales = theta(24:30);

%% Measurement matrix
H = zeros(7, n_states);

% Quarterly GDP: Mariano-Murasawa-style aggregation over five monthly
% factor states plus the five GDP-idiosyncratic states.
H(1, 1:5) = loadings(1) * quarterly_weights;
H(1, 13:17) = quarterly_weights;

% Hard monthly indicators load contemporaneously on the common factor.
H(2, 1) = loadings(2);   % IPI
H(4, 1) = loadings(4);   % retail sales

% Variables expressed as 12-month growth load on the current factor and
% its previous 11 monthly states.
H(3, 1:12) = loadings(3);   % affiliation y/y
H(5, 1:12) = loadings(5);   % imports y/y
H(6, 1:12) = loadings(6);   % tourism y/y

% ESI is kept in levels and, following the course specification, is treated
% as a soft indicator that loads on the current factor and 11 monthly lags.
H(7, 1:12) = loadings(7);

% Current idiosyncratic states for the six monthly indicators.
monthly_state_starts = 18:2:28;
for j = 1:6
    H(j + 1, monthly_state_starts(j)) = 1;
end

%% Transition matrix
F = zeros(n_states, n_states);

% Common factor AR(2) with 12 stored monthly states.
F(1, 1:2) = ar_pairs(1, :);
F(2:12, 1:11) = eye(11);

% GDP idiosyncratic AR(2) with five stored states.
F(13, 13:14) = ar_pairs(2, :);
F(14:17, 13:16) = eye(4);

% Six monthly idiosyncratic AR(2) blocks.
for j = 1:6
    first = monthly_state_starts(j);
    F(first, first:first+1) = ar_pairs(j + 2, :);
    F(first + 1, first) = 1;
end

%% State-shock covariance
Q = zeros(n_states, n_states);
Q(1, 1) = 1;  % factor-shock variance fixes the factor scale
Q(13, 13) = shock_scales(1)^2;
for j = 1:6
    first = monthly_state_starts(j);
    Q(first, first) = shock_scales(j + 1)^2;
end
end
