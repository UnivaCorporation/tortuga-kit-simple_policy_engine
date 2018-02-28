#######################################################################
##                                                                   ##
##   Copyright (c) 2011-2017, Univa.  All rights reserved.           ##
##   Copyright (c) 2010, Univa UD.  All rights reserved.             ##
##   http://univa.com                                                ##
##                                                                   ##
##   License:                                                        ##
##     Tortuga Draft                                                ##
##                                                                   ##
##   Description:                                                    ##
##                                                                   ##
##                                                                   ##
#######################################################################

class tortuga_kit_simple_policy_engine::engine::package {
  require tortuga::packages

  ensure_packages(['libxml2'], {'ensure' => 'installed'})
}

class tortuga_kit_simple_policy_engine::engine::config {
  include tortuga_kit_simple_policy_engine::config

  require tortuga_kit_simple_policy_engine::engine::package

  tortuga::run_post_install { 'tortuga_kit_policy_engine_post_install':
    kitdescr  => $tortuga_kit_simple_policy_engine::config::kitdescr,
    compdescr => $tortuga_kit_simple_policy_engine::engine::compdescr,
  }
}

class tortuga_kit_simple_policy_engine::engine {
  include tortuga_kit_simple_policy_engine::config

  $compdescr = "engine-${tortuga_kit_simple_policy_engine::config::major_version}"

  contain tortuga_kit_simple_policy_engine::engine::package
  contain tortuga_kit_simple_policy_engine::engine::config

  Class['tortuga_kit_simple_policy_engine::engine::config'] ~>
    Class['tortuga_kit_base::installer::webservice::server']
}
