"""
  Implements some utilities for Cartesian Product GPs.
  - The term config refers to a namespace that stores information about the optimisation
    problem. Typically, it is what is returened by the load_config_file function.
  -- kandasamy@cs.cmu.edu
"""

# pylint: disable=invalid-name

from argparse import Namespace
# Local imports
from . import domains
from ..parse.config_parser import config_parser
from ..utils.general_utils import flatten_list_of_objects_and_iterables, \
                                get_original_order_from_reordered_list, \
                                transpose_list_of_lists
from ..utils.oper_utils import random_sample_from_euclidean_domain, \
                             random_sample_from_integral_domain, \
                             random_sample_from_prod_discrete_domain


def _process_fidel_to_opt(raw_fidel_to_opt, fidel_space, fidel_space_orderings,
                          config_file):
  """ Processes and returns fidel_to_opt. """
  if raw_fidel_to_opt is None:
    fidel_to_opt = None
    from warnings import warn
    warn('fidel_to_opt is None for %s.'%(config_file))
  else:
    try:
      fidel_to_opt = get_processed_point_from_raw_point(raw_fidel_to_opt,
                       fidel_space, fidel_space_orderings.index_ordering,
                       fidel_space_orderings.dim_ordering)
      assert fidel_space.is_a_member(fidel_to_opt)
    except:
      raise ValueError('fidel_to_opt: %s (raw: %s) is not a member of fidel_space %s.'%(
                       fidel_to_opt, raw_fidel_to_opt, fidel_space))
  # Return
  return raw_fidel_to_opt, fidel_to_opt


def load_config_file(config_file, *args, **kwargs):
  """ Loads the configuration file. """
  parsed_result = config_parser(config_file)
  domain_params = parsed_result['domain']
  domain, domain_orderings = load_domain_from_params(domain_params, *args, **kwargs)
  config = Namespace(name=parsed_result['exp_info']['name'],
                     domain=domain, domain_orderings=domain_orderings)
  # Check the fidelity space
  if 'fidel_space' in parsed_result.keys():
    fidel_space_params = parsed_result['fidel_space']
    fidel_space, fidel_space_orderings = load_domain_from_params(
                                           fidel_space_params, *args, **kwargs)
    if len(fidel_space.list_of_domains) > 0:
      config.fidel_space = fidel_space
      config.fidel_space_orderings = fidel_space_orderings
      config.raw_fidel_to_opt, config.fidel_to_opt = _process_fidel_to_opt(
        parsed_result['fidel_to_opt'], fidel_space, fidel_space_orderings, config_file)
  return config


def load_cp_domain_from_config_file(config_file, *args, **kwargs):
  """ Loads and creates a cartesian product domain object from a config_file. """
  parsed_result = config_parser(config_file)
  domain_params = parsed_result['domain']
  return load_domain_from_params(domain_params, *args, **kwargs)


def load_domain_from_params(domain_params,
      general_euclidean_kernel='', general_integral_kernel='',
      general_discrete_kernel='', general_discrete_numeric_kernel=''):
  """ Loads and creates a cartesian product object from a config_file. """
  # pylint: disable=too-many-branches
  # pylint: disable=too-many-statements
  # pylint: disable=too-many-locals
  # pylint: disable=unused-argument
  list_of_domains = []
  general_euclidean_bounds = []
  general_euclidean_idxs = []
  general_integral_bounds = []
  general_integral_idxs = []
  general_discrete_items_list = []
  general_discrete_idxs = []
  general_discrete_numeric_items_list = []
  general_discrete_numeric_idxs = []
  # We will need the following variables for the function caller and the kernel
  index_ordering = [] # keeps track of which index goes where in the domain
  # iterate over the loop
  for idx, param in enumerate(domain_params):
    if param['type'] in ['float', 'int']:
      bound_dim = 1 if param['dim'] == '' else param['dim']
      curr_bounds = [[param['min'], param['max']]] * bound_dim
    elif param['type'] in ['discrete', 'discrete_numeric']:
      items_dim = 1 if param['dim'] == '' else param['dim']
      curr_items = [param['items']] * items_dim
    # Now append to relevant part
    if param['type'] == 'float':
      if param['kernel'] == '':
        general_euclidean_bounds.extend(curr_bounds)
        general_euclidean_idxs.append(idx)
      else:
        list_of_domains.append(domains.EuclideanDomain(curr_bounds))
        index_ordering.append(idx)
    elif param['type'] == 'int':
      if param['kernel'] == '':
        general_integral_bounds.extend(curr_bounds)
        general_integral_idxs.append(idx)
      else:
        list_of_domains.append(domains.IntegralDomain(curr_bounds))
        index_ordering.append(idx)
    elif param['type'] == 'discrete':
      if param['kernel'] == '':
        general_discrete_items_list.extend(curr_items)
        general_discrete_idxs.append(idx)
      else:
        list_of_domains.append(domains.ProdDiscreteDomain(curr_items))
        index_ordering.append(idx)
    elif param['type'] == 'discrete_numeric':
      if param['kernel'] == '':
        general_discrete_numeric_items_list.extend(curr_items)
        general_discrete_numeric_idxs.append(idx)
      else:
        list_of_domains.append(domains.ProdDiscreteNumericDomain(curr_items))
        index_ordering.append(idx)
    elif param['type'].startswith(('nn', 'cnn', 'mlp')):
      from nn.nn_domains import get_nn_domain_from_constraints
      list_of_domains.append(get_nn_domain_from_constraints(param['type'], param))
      index_ordering.append(idx)
    else:
      raise ValueError('Unknown domain type: %s.'%(param['type']))
  # Create kernel ordering and variable ordering
  kernel_ordering = [domain_params[idx]['kernel'] for idx in index_ordering]
  name_ordering = [domain_params[idx]['name'] for idx in index_ordering]
  dim_ordering = [domain_params[idx]['dim'] for idx in index_ordering]
  # For general euclidean and integral domains
  if len(general_euclidean_bounds) > 0:
    list_of_domains.append(domains.EuclideanDomain(general_euclidean_bounds))
    general_euclidean_names = [domain_params[idx]['name'] for idx in
                               general_euclidean_idxs]
    general_euclidean_dims = [domain_params[idx]['dim'] for idx in general_euclidean_idxs]
    name_ordering.append(general_euclidean_names)
    dim_ordering.append(general_euclidean_dims)
    index_ordering.append(general_euclidean_idxs)
    kernel_ordering.append(general_euclidean_kernel)
  if len(general_integral_bounds) > 0:
    list_of_domains.append(domains.IntegralDomain(general_integral_bounds))
    general_integral_names = [domain_params[idx]['name'] for idx in general_integral_idxs]
    general_integral_dims = [domain_params[idx]['dim'] for idx in general_integral_idxs]
    name_ordering.append(general_integral_names)
    dim_ordering.append(general_integral_dims)
    index_ordering.append(general_integral_idxs)
    kernel_ordering.append(general_integral_kernel)
  if len(general_discrete_items_list) > 0:
    list_of_domains.append(domains.ProdDiscreteDomain(general_discrete_items_list))
    general_discrete_names = [domain_params[idx]['name'] for idx in general_discrete_idxs]
    general_discrete_dims = [domain_params[idx]['dim'] for idx in general_discrete_idxs]
    name_ordering.append(general_discrete_names)
    dim_ordering.append(general_discrete_dims)
    index_ordering.append(general_discrete_idxs)
    kernel_ordering.append(general_discrete_kernel)
  if len(general_discrete_numeric_items_list) > 0:
    list_of_domains.append(
      domains.ProdDiscreteNumericDomain(general_discrete_numeric_items_list))
    general_discrete_numeric_names = \
      [domain_params[idx]['name'] for idx in general_discrete_numeric_idxs]
    general_discrete_numeric_dims = \
      [domain_params[idx]['dim'] for idx in general_discrete_numeric_idxs]
    name_ordering.append(general_discrete_numeric_names)
    dim_ordering.append(general_discrete_numeric_dims)
    index_ordering.append(general_discrete_numeric_idxs)
    kernel_ordering.append(general_discrete_numeric_kernel)
  # Create a cartesian product domain
  cp_domain = domains.CartesianProductDomain(list_of_domains)
  # Arrange all orderings into a namespace
  orderings = Namespace(index_ordering=index_ordering,
                        kernel_ordering=kernel_ordering,
                        dim_ordering=dim_ordering,
                        name_ordering=name_ordering)
  return cp_domain, orderings


def get_num_raw_domains(ordering):
  """ Returns the number of raw domains. """
  num_raw_domains = len(ordering)
  for elem in ordering:
    if hasattr(elem, '__iter__'):
      num_raw_domains += len(elem) - 1
  return num_raw_domains


def _unpack_vectorised_domain(x, dim_ordering):
  """ Unpacks a vectorised domain. """
  ret = [None] * len(dim_ordering)
  counter = 0
  for idx, num_dims in enumerate(dim_ordering):
    if num_dims == '':
      ret[idx] = x[counter]
      counter += 1
    else:
      ret[idx] = x[counter:counter+num_dims]
      counter += num_dims
  assert counter == len(x) # TODO: remove this assertion (for debugging only).
  return ret


# Functions to pack and unpack points in the domain -----------------------------------
def get_processed_point_from_raw_point(raw_x, cp_domain, index_ordering, dim_ordering):
  """ Obtains the processed point from the raw point. """
  if not cp_domain.get_type() == 'cartesian_product':
    packed_x = [raw_x[index_ordering[j]] for j in index_ordering]
    return flatten_list_of_objects_and_iterables(packed_x)
  else:
    packed_x = [None] * len(index_ordering)
    for idx, idx_order in enumerate(index_ordering):
      if isinstance(idx_order, list):
        curr_elem = [raw_x[j] for j in idx_order]
        curr_elem = flatten_list_of_objects_and_iterables(curr_elem)
        packed_x[idx] = curr_elem
      elif dim_ordering[idx] == '' and (cp_domain.list_of_domains[idx].get_type() in \
                     ['euclidean', 'integral', 'prod_discrete', 'prod_discrete_numeric']):
        packed_x[idx] = [raw_x[idx_order]]
      else:
        packed_x[idx] = raw_x[idx_order]
    return packed_x


def get_raw_point_from_processed_point(proc_x, cp_domain, index_ordering, dim_ordering):
  """ Gets the raw point from the processed point. """
  if not cp_domain.get_type() == 'cartesian_product':
    repacked_x = _unpack_vectorised_domain(proc_x, dim_ordering)
  else:
    repacked_x = []
    for idx, raw_dim in enumerate(dim_ordering):
      if isinstance(raw_dim, list):
        repacked_x.append(_unpack_vectorised_domain(proc_x[idx], raw_dim))
      elif raw_dim == '':
        repacked_x.append(proc_x[idx])
      else:
        repacked_x.append([proc_x[idx]])
    repacked_x = flatten_list_of_objects_and_iterables(repacked_x)
  flattened_index_ordering = flatten_list_of_objects_and_iterables(index_ordering)
  x_orig_order = get_original_order_from_reordered_list(repacked_x,
                                                        flattened_index_ordering)
  return x_orig_order


def get_raw_from_processed_via_config(proc_point, config):
  """ Gets the raw point (both domain and fidel) from the processed point. """
  has_fidel = hasattr(config, 'fidel_space')
  if has_fidel:
    proc_fidelity, proc_dom_point = proc_point
  else:
    proc_dom_point = proc_point
  raw_dom_point = get_raw_point_from_processed_point(proc_dom_point, config.domain,
    config.domain_orderings.index_ordering, config.domain_orderings.dim_ordering)
  if has_fidel:
    raw_fidelity = get_raw_point_from_processed_point(proc_fidelity, config.fidel_space,
                                              config.fidel_space_orderings.index_ordering,
                                              config.fidel_space_orderings.dim_ordering)
    return [raw_fidelity, raw_dom_point]
  else:
    return raw_dom_point


def get_processed_from_raw_via_config(raw_point, config):
  """ Gets the processed point (both domain and fidel) from the raw point. """
  has_fidel = hasattr(config, 'fidel_space')
  if has_fidel:
    raw_fidelity, raw_dom_point = raw_point
  else:
    raw_dom_point = raw_point
  proc_dom_point = get_processed_point_from_raw_point(raw_dom_point, config.domain,
    config.domain_orderings.index_ordering, config.domain_orderings.dim_ordering)
  if has_fidel:
    proc_fidelity = get_processed_point_from_raw_point(raw_fidelity, config.fidel_space,
                      config.fidel_space_orderings.index_ordering,
                      config.fidel_space_orderings.dim_ordering)
    return [proc_fidelity, proc_dom_point]
  else:
    return proc_dom_point


# Functions to sample from cp_domain ----------------------------------------------------
def sample_from_cp_domain(cp_domain, num_samples, domain_samplers=None,
                          euclidean_sample_type='rand',
                          integral_sample_type='rand',
                          nn_sample_type='rand'):
  """ Samples from the CP domain. """
  if domain_samplers is None:
    domain_samplers = [None] * cp_domain.num_domains
  individual_domain_samples = []
  for idx, dom in enumerate(cp_domain.list_of_domains):
    if domain_samplers[idx] is not None:
      curr_domain_samples = domain_samplers[idx](num_samples)
    else:
      if dom.get_type() == 'euclidean':
        curr_domain_samples = random_sample_from_euclidean_domain(dom.bounds, num_samples,
                                                                  euclidean_sample_type)
      elif dom.get_type() == 'integral':
        curr_domain_samples = random_sample_from_integral_domain(dom.bounds, num_samples,
                                                                 integral_sample_type)
      elif dom.get_type() in ['prod_discrete', 'prod_discrete_numeric']:
        curr_domain_samples = random_sample_from_prod_discrete_domain(
                                dom.list_of_list_of_items, num_samples)
      elif dom.get_type() == 'neural_network':
        from nn.nn_opt_utils import random_sample_from_nn_domain
        curr_domain_samples = random_sample_from_nn_domain(dom.nn_type, num_samples,
                                                           nn_sample_type,
                                                           dom.constraint_checker)
      else:
        raise ValueError('Unknown domain type %s. Provide sampler.'%(dom.get_type()))
      individual_domain_samples.append(curr_domain_samples)
  return transpose_list_of_lists(individual_domain_samples)


def sample_from_config_space(config, num_samples,
                             fidel_space_samplers=None,
                             domain_samplers=None,
                             fidel_space_euclidean_sample_type='rand',
                             fidel_space_integral_sample_type='rand',
                             domain_euclidean_sample_type='rand',
                             domain_integral_sample_type='rand',
                             domain_nn_sample_type='rand',
                             ):
  """ Samples from the Domain and possibly the fidelity space. """
  domain_samples = sample_from_cp_domain(config.domain, num_samples, domain_samplers,
    domain_euclidean_sample_type, domain_integral_sample_type, domain_nn_sample_type)
  if hasattr(config, 'fidel_space'):
    fidel_space_samples = sample_from_cp_domain(config.fidel_space, num_samples,
      fidel_space_samplers, fidel_space_euclidean_sample_type,
      fidel_space_integral_sample_type)
    return [list(x) for x in zip(fidel_space_samples, domain_samples)]
  else:
    return domain_samples


# Functions to get processed raw function -----------------------------------------------
def get_processed_func_from_raw_func_for_cp_domain(raw_func, cp_domain,
                                                   index_ordering, dim_ordering):
  """ Returns a processed function from the raw function based on the ordering.
  """
  # This function does the evaluation.
  def _eval_func_x_after_unpacking(x, _raw_func, _cp_domain, _index_ordering,
                                   _dim_ordering):
    """ Evaluates the function after processing it. """
    return _raw_func(get_raw_point_from_processed_point(x, _cp_domain, _index_ordering,
                                                        _dim_ordering))
  # This function returns the raw function
  def _get_processed_func(_raw_func, _cp_domain, _index_ordering, _dim_ordering):
    """ Returns a function which evaluates raw_func from a packed input. """
    return lambda x: _eval_func_x_after_unpacking(x, _raw_func, _cp_domain,
                                                  _index_ordering, _dim_ordering)
  # Return
  return _get_processed_func(raw_func, cp_domain, index_ordering, dim_ordering)


def get_processed_func_from_raw_func_for_cp_domain_fidelity(raw_func, config):
  """ Returns a processed function from the raw function based on the ordering.
  """
  # This function does the evaluation.
  def _eval_func_z_x_after_unpacking(z, x, _raw_func, _fidel_space, _domain,
    _fidel_space_index_ordering, _fidel_space_dim_ordering,
    _domain_index_ordering, _domain_dim_ordering):
    """ Evaluates the function after processing it. """
    raw_z = get_raw_point_from_processed_point(z, _fidel_space,
              _fidel_space_index_ordering, _fidel_space_dim_ordering)
    raw_x = get_raw_point_from_processed_point(x, _domain,
              _domain_index_ordering, _domain_dim_ordering)
    return _raw_func(raw_z, raw_x)
  # This returns the raw function
  def _get_processed_func(_raw_func, _fidel_space, _domain,
    _fidel_space_index_ordering, _fidel_space_dim_ordering,
    _domain_index_ordering, _domain_dim_ordering):
    """ Evaluates the function after processing it. """
    return lambda z, x: _eval_func_z_x_after_unpacking(z, x, _raw_func,
      _fidel_space, _domain, _fidel_space_index_ordering, _fidel_space_dim_ordering,
      _domain_index_ordering, _domain_dim_ordering)
  # Return
  return _get_processed_func(raw_func, config.fidel_space, config.domain,
                             config.fidel_space_orderings.index_ordering,
                             config.fidel_space_orderings.dim_ordering,
                             config.domain_orderings.index_ordering,
                             config.domain_orderings.dim_ordering)


def get_processed_func_from_raw_func_via_config(raw_func, config):
  """ Returns a processed function from the raw function based on the ordering.
  """
  if hasattr(config, 'fidel_space'):
    return get_processed_func_from_raw_func_for_cp_domain_fidelity(raw_func, config)
  else:
    return get_processed_func_from_raw_func_for_cp_domain(raw_func, config.domain,
             config.domain_orderings.index_ordering, config.domain_orderings.dim_ordering)

