import argparse
import os

from moleculekit.molecule import Molecule
import numpy as np


def get_parser():
    parser = argparse.ArgumentParser(
        description='This script modifies rmsf.xvg generated by GROMACS to the input format of DEFMap.',
        usage='usage'
    )
    parser.add_argument(
        '-p', '--pdb', action='store', default=None, required=True,
        help='original pdb'
    )
    parser.add_argument(
        '-g', '--gromacs_pdb', action='store', default=None, required=True,
        help='coordinate file created by a pdb2gmx module in GROMACS.'
    )
    parser.add_argument(
        '-x', '--xvg', action='store', default=None, required=True,
        help='original xvg file'
    )
    return parser.parse_args()


def conv_atom_name_in_gropdb(mol_md):
    # edit atom name of conf.pdv to pdb format
    mol_md.name = np.where((mol_md.name == 'CD') & (mol_md.resname == 'ILE'), 'CD1', mol_md.name)  # for conversion from .gro format to .pdb format
    mol_md.name = np.where(mol_md.name == 'OC2', 'O', mol_md.name)  # for conversion from .gro format to .pdb format
    mol_md.name = np.where(mol_md.name == 'OC1', 'OXT', mol_md.name)  # for conversion from .gro format to .pdb format
    mol_md.filter('protein')
    return mol_md
    

def make_unique_chain_name_list(mol_org):
    _, chidx = np.unique(mol_org.chain, return_index=True)
    chid = mol_org.chain[np.sort(chidx)]
    return chid


def make_chain_name_list_for_gropdb(mol_md, chid_uniq, exception_resid_chid_list_case1, exception_resid_chid_list_case2):
    ct = 0
    md_chids = []
    atom_list = []
    for r in range(len(mol_md.resid)-1):
        target_rid_md = mol_md.resid[r]
        target_aname_md = mol_md.name[r]
        next_aname_md = mol_md.name[r+1]
        next_rid_md = mol_md.resid[r+1]
        incr_resid_num_md = next_rid_md - target_rid_md
        if incr_resid_num_md < 0:
            md_chids, ct = CASE_0(md_chids, chid_uniq, ct)
        elif f'{target_rid_md}{chid_uniq[ct]}' in exception_resid_chid_list_case1:
            md_chids, ct, atom_list = CASE_1(incr_resid_num_md, target_aname_md, next_aname_md, md_chids, chid_uniq, ct, atom_list)
        elif f'{target_rid_md}{chid_uniq[ct]}' in exception_resid_chid_list_case2:
            md_chids, ct = CASE_2(incr_resid_num_md, md_chids, chid_uniq, ct)
        else:
            md_chids.append(chid_uniq[ct])
    md_chids.append(chid_uniq[ct])
    return md_chids    


def CASE_0(md_chids, chid_uniq, ct):
    md_chids.append(chid_uniq[ct])
    ct += 1
    return md_chids, ct


def CASE_1(incr_resid_num_md, target_aname_md, next_aname_md, md_chids, chid_uniq, ct, atom_list):
    if incr_resid_num_md == 0 and target_aname_md not in atom_list:
        md_chids.append(chid_uniq[ct])
        atom_list.append(target_aname_md)
        if next_aname_md in atom_list:
            ct += 1
            atom_list = []
    return md_chids, ct, atom_list


def CASE_2(incr_resid_num_md, md_chids, chid_uniq, ct):
    if incr_resid_num_md == 0:
        md_chids.append(chid_uniq[ct])
    elif incr_resid_num_md != 0:
        md_chids.append(chid_uniq[ct])
        ct += 1
    return md_chids, ct


def add_chain_id_to_gropdb(mol_org, mol_md):
    rid_CA = mol_org.get('resid', sel='name CA')
    chid_CA = mol_org.get('chain', sel='name CA')

    """
    "exception_resid_chid_list" contains the C-term. resid-chid name,
    whose next resid number (the N-term. residue of the next chain)
    is unchanged (CASE 1) or increased (CASE 2).
    The C-term. resid-chid name, whose next resid number is decreased (CASE 0),
    is not contained.
    """
    exception_resid_chid_list_case1, exception_resid_chid_list_case2 = [], []
    for i in range(len(rid_CA)-1):
        target_rid = rid_CA[i]
        target_chid = chid_CA[i]
        next_rid = rid_CA[i+1]
        next_chid = chid_CA[i+1]
        incr_resid_num = next_rid - target_rid 
        if incr_resid_num < 0:
            continue
        else:
            if next_chid != target_chid:
                if incr_resid_num == 0:
                    exception_resid_chid_list_case1.append(f'{rid_CA[i]}{chid_CA[i]}')
                elif incr_resid_num > 0:
                    exception_resid_chid_list_case2.append(f'{rid_CA[i]}{chid_CA[i]}')
     
    chid_uniq = make_unique_chain_name_list(mol_org)
    md_chids = make_chain_name_list_for_gropdb(mol_md, chid_uniq, exception_resid_chid_list_case1, exception_resid_chid_list_case2)
    mol_md.set('chain', md_chids)
    return mol_md


def make_list_extracted_md_serials(mol_org, mol_md):
    mol_org_rid_rname_cid_aname = [f'{ri}{rn}{ci}{an}'
                                   for ri, rn, ci, an
                                   in zip(mol_org.resid, mol_org.resname, mol_org.chain, mol_org.name)]
    md_rid_rname_cid_aname = {f'{ri}{rn}{ci}{an}': i
                              for i, (ri, rn, ci, an)
                              in enumerate(zip(mol_md.resid, mol_md.resname, mol_md.chain, mol_md.name))}

    extracted_md_serials = {f"{mol_md.serial[md_rid_rname_cid_aname.get(x)]}": i
                            for i, x in enumerate(mol_org_rid_rname_cid_aname)}
    return extracted_md_serials


def get_processed_serial_and_label(mol_org, xvg, extracted_md_serials):
    with open(xvg, 'r') as f:
        f = f.readlines()
        md_serial_ids = [i.split()[0] for i in f if i[0] != '#' and i[0] != '@']
        rmsf_vals = [float(i.split()[1])*10 for i in f if i[0] != '#' and i[0] != '@']
    pdb_serial_ids = []
    extracted_rmsf_vals = []
    for s, v in zip(md_serial_ids, rmsf_vals):
        if s in extracted_md_serials.keys():
            idx = extracted_md_serials.get(s)
            pdb_serial_ids.append(mol_org.serial[idx])
            extracted_rmsf_vals.append(float(v))
    return np.asarray(pdb_serial_ids), np.asarray(extracted_rmsf_vals)


def save_processed_tbl(mol_org, xvg, extracted_md_serials):
    with open(xvg, 'r') as f:
        f = f.readlines()
        md_serial_ids = [int(i.split()[0]) for i in f if i[0] != '#' and i[0] != '@']
        rmsf_vals = [float(i.split()[1]) for i in f if i[0] != '#' and i[0] != '@']

    print(f'[INFO] processing for {xvg}')
    filename = os.path.join(os.path.dirname(xvg), f'{os.path.splitext(os.path.basename(xvg))[0]}_processed.tbl')
    with open(filename, 'w') as fw:
        fw.write('#serial numbers were converted from in conf.pdb to in input.pdb\n')
        rmsf_serid_pdbs = [f'{mol_org.serial[extracted_md_serials.index(s)]}\t{v}\t{s}'
                           for s, v
                           in zip(md_serial_ids, rmsf_vals)
                           if s in extracted_md_serials]
        out = "\n".join(rmsf_serid_pdbs)
        fw.write(out)
    print('[INFO] Done.')
    

def main():
    args = get_parser()
    mol_org = Molecule(args.pdb)
    mol_org.filter('protein')
    mol_md = Molecule(args.gromacs_pdb)
    mol_md = conv_atom_name_in_gropdb(mol_md)
    mol_md = add_chain_id_to_gropdb(mol_org, mol_md)
    extracted_md_serials_from_xvg = make_list_extracted_md_serials(mol_org, mol_md)
    save_processed_tbl(mol_org, args.xvg, extracted_md_serials_from_xvg)


if __name__ == "__main__":
    main()
