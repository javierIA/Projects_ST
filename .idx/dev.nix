{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-23.11"; # or "unstable"

  # Use https://search.nixos.org/packages to find packages
  packages = [
    pkgs.python311 # Or another version like pkgs.python310
    pkgs.python311Packages.pip
  ];

  # Sets environment variables in the workspace
  env = {
    PYTHONPATH = "${pkgs.python311}/lib/python3.11/site-packages";
    # Add other environment variables as needed
  };

  # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
  idx.extensions = [
    "ms-python.python" # Official Python extension for VS Code
    "njpwerner.autodocstring" # Example: Extension for generating docstrings
  ];

  # Enable previews and customize configuration
  idx.previews = {
    enable = true; # No web preview for this example
    # previews = {
    previews.web = {
       command = [
         "pip" "install" "-r" "requirements.txt"
         "python"
         "main.py"
       ];
       manager = "web";
    };
  };
}