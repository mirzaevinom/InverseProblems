# -*- coding: utf-8 -*-

"""
Created on May 15, 2016
@author: Inom Mirzaev

Simulates the inverse problem for different values of sigma (standard deviation of the error)

Distributes the optimization into multiple proccess. 

"""



from __future__ import division

import numpy as np
import time
import cPickle, os
import model_rates as mr

from scipy import interpolate
from functools import partial
from multiprocessing import Pool
from scipy.integrate import odeint
from scipy.optimize import  fmin_cobyla


start = time.time()

print 'Start time', time.strftime( "%H:%M" , time.localtime() )



def estimator( sigma ):
    
    """takes as standard deviation sigma as an argument 
    and returns the optimization results for this sigma"""

    #Initialization of the matrices required for the simulations
    Ain, Aout, Fin, Fout, nu, N, dx = mr.initialization( 30 )    

    xx , yy = np.meshgrid( nu[1:] , nu[1:] )
 
    #Initial guess of gamma function for the optimization   
    init_P = mr.init_gam( xx , yy)    
    
    
    data_t = np.linspace( 0 , mr.tfinal , 20 )
    data_x = np.linspace( mr.x0 , mr.x1 , 11)
                
    data = mr.interp_data( data_x , data_t , sigma=sigma)
    
    
    # Same as data_generator, except for the Fin matrix
    myderiv = partial( mr.odeRHS , Ain=Ain, Aout=Aout, Fout=Fout, nu = nu, dx = dx)

    y0 = mr.ICproj( N )
    mytime = np.linspace( 0 , mr.tfinal , 100 ) 
  
    def optim_func( P, data=data, y0=y0, N=N , t=mytime ,  data_x = data_x , data_t = data_t):
        
        """Argument P is 1D array with entries of Gamma function evaluated at a matrix.
           Simulates the forward problem with this P and returns the least squares sum. """
        
        #Initiliaze Gamma with P
        Gamma = np.zeros( ( N , N ) )
        Gamma[ np.tril_indices(N, -1) ] = P
        
        #Simulate the forward problem with this Gamma
        
        yout = odeint( myderiv , y0 , t , args=( Gamma , N ) , 
              printmessg=False, rtol=1e-3, atol=1e-5 , full_output = False)
        
        
        #Interpolate ODE results to the data grid
        interp_x = np.linspace(mr.x0 , mr.x1 , N)
        func = interpolate.interp2d( interp_x , t , yout )


        fit = np.zeros_like( data )
    
        for mm in range( len(data_x) - 1):
            
            #Integrates using trapezoidal rule with 10 discrete points intepolated from yout            
            int_grid = np.linspace( data_x[mm] , data_x[mm+1] , 10)            
            fit[ : , mm] = np.trapz( func( int_grid , data_t ) , int_grid , axis=1 )

        return  np.sum( ( fit - data ) **2 ) 

    
    #Initial seed for the optimization
    seed = init_P[ np.tril_indices(N, -1) ]
    
    def P2Gamma(P):
        """Converts 1D array P to 2D array Gamma.
           Returns inequality that should be positive.
           Integral of each row of Gamma needs to be less than one"""
        Gamma = np.zeros( ( N , N ) )
        Gamma[ np.tril_indices(N,-1) ] = P
        
        return 1 - dx*np.sum( Gamma , axis=1 )

    def neg_ineqs(j):
        """Returns functions handles for the individual inequalities."""        
        return lambda P : P2Gamma(P)[j] 
        
    def ineqs(j):
        """Each entry of P needs to be positive"""
        return lambda P: P[j]
     
    
    #List of inequalites
    ineq1 = [ neg_ineqs(j) for j in range(N ) ] 
    ineq2 = [ineqs(j) for j in range( len(seed) ) ]    
    cons = ineq2 + ineq1
    
    #Optimization with fmin_cobyla, which uses Powell's direct search method.
    
    res = fmin_cobyla( optim_func , seed, cons  , maxfun=10000 , rhobeg=1 , rhoend=1)     

    #Converts 1D results to Gamma_fit
    G_fit = np.zeros( ( N , N ) )
    G_fit[ np.tril_indices(N,-1) ] = res

    #Get F_fit from Gamma_fit
    f_fit = np.zeros( ( N , N ) )
    f_fit  = np.cumsum( dx * G_fit, axis=1)
    f_fit[np.triu_indices(N) ]  = 1

    
    #Compute F_true
    f_true = np.zeros( ( N , N ) )    
    true_P = mr.gam( xx , yy )
    f_true  =np.cumsum( dx * true_P , axis = 1 )
    f_true[np.triu_indices(N) ]  = 1
    
    #Compute F_initial
    
    f_init = np.zeros( ( N , N ) ) 
    f_init = np.cumsum( dx * init_P , axis = 1)
    f_init[np.triu_indices(N) ]  = 1 

    
    return (sigma,  res , f_init, f_true, f_fit)
    

if __name__ == '__main__':
    
    #Usually number of CPUs is good number for number of proccess
    pool = Pool( processes = 4 )
    ey_nana =  np.linspace(0, 50 , 20)

    result = pool.map(estimator, ey_nana)
    
    #Save the output *.pkl file for later manipulations
    fname = 'data_' + time.strftime( "%m_%d_%H_%M_" , time.localtime() ) + str(mr.a) + '_noise.pkl'   
    output_file = open( os.path.join( 'data_files' , fname ) , 'wb')
    cPickle.dump(result, output_file)
    output_file.close()

