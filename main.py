import sys
import os
import argparse
import cloudformation
import analyser

def get_cf_path(code_dir, framework):
    """ Looks for CloudFormation json files relevant for the provided framework
    """
    if framework == 'serverless':
        relevant_dir = os.path.join(code_dir, '.serverless')
        create_stack_file = os.path.join(relevant_dir, 'cloudformation-template-create-stack.json')
        update_stack_file = os.path.join(relevant_dir, 'cloudformation-template-update-stack.json')
        if os.path.exists(update_stack_file):
            return update_stack_file
        else:
            return create_stack_file

def main():

    parser = argparse.ArgumentParser(description='PureSec Least Privilege Role Creator')
    parser.add_argument('--code_dir',
                        action="store",
                        dest="code_dir",
                        help="Path to base directory for functions code")
    parser.add_argument('--framework',
                        action="store",
                        dest="framework",
                        help="Framework used for deploying")
    parser.add_argument('--cf_path',
                        action="store",
                        dest="cf_template_path",
                        help="CloudFormation json path")



    args = parser.parse_args()

    code_dir = args.code_dir

    if 'cf_path' not in args:
        if 'framework' not in args:
            print "Please provide CloudFormation path or used Framework."
        else:
            framework = args.framework
            cf_path = get_cf_path(code_dir, framework)
    else:
        cf_path = args.cf_template_path

    cf = cloudformation.CloudFormation(cf_path=cf_path)
    cf.parse()

    an = analyser.Analyser(cf, code_dir, framework)
    an.get_minimal_roles_from_code()



if __name__ == "__main__":
    main()
