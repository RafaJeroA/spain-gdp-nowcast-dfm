function [z, means, stdevs] = standardize_observed(y)
%STANDARDIZE_OBSERVED Standardise each column using observed values only.

z = nan(size(y));
means = nan(1, size(y, 2));
stdevs = nan(1, size(y, 2));

for j = 1:size(y, 2)
    observed = isfinite(y(:, j));
    values = y(observed, j);
    if isempty(values)
        error('Column %d has no observed values.', j);
    end

    means(j) = mean(values);
    stdevs(j) = std(values, 1);
    if ~isfinite(stdevs(j)) || stdevs(j) <= 0
        error('Column %d has zero or invalid standard deviation.', j);
    end

    z(observed, j) = (values - means(j)) / stdevs(j);
end
end
