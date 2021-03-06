# -*- coding: utf-8 -*-
#Created on Feb 18, 2016
#@author: Inom Mirzaev

"""
    Model rates and parameters used for identifying conditional probability measures. 
    See Bortz, D. M., Byrne C. E. and Mirzaev, I. (2016). 
"""


from __future__ import division
from scipy.integrate import quad, odeint
from scipy import interpolate
from scipy.special import beta 
from functools import partial

import scipy.linalg as lin
import numpy as np



# Minimum and maximum floc sizes
x0 = 0
x1 = 1

#Beta function parameters
a = 5
b = 1

#initial guess
c = 1

def init_gam( y , x , c=c ):
    
    """Ininitial guess for gamma function. Uniform distribution"""    

    out = y**(c-1) * ( x - y )**(c-1)  / ( x**(2*c-1) ) / beta( c , c )
    out[y>x] = 0
    
    return out    


def gam( y , x , a=a, b=b):
    
    """True post-fragmentation density distribution
       used for data generation."""
       
    out = y**(a-1) * ( np.abs( x - y )**(b-1) )  / ( x**(a+b-1) ) / beta( a , b )
    
    if type(x) == np.ndarray or type(y) == np.ndarray:        
        out[y>x] = 0
        out[ np.isnan(out) ] = 0    
        out[ np.isinf(out) ] = 0  

    return out 

def aggregation( x , y ):
 
    """Aggregation rate"""   
    out = ( x ** ( 1/3 ) + y ** ( 1/3 ) ) **3 / (10**6)    
    #Should return a vector
    return out


    
    
def rem( x ):
     """Removal rate"""
     #Should return a vector
     return 1e-3*x**(1/3)

     
def fragm( x ):
    """Fragmentation rate"""   
    #Should return a vector
    return  1e-1 * x**(1/3)

    
def incond(x):
    """Initial condition"""   
    return 1e3 * np.exp( x )



#Projection function for the initial condition
def ICproj( N ):
    
     dx=( x1 - x0 ) / N
     nu=x0 + np.arange(N+1) * dx
     
     out=np.zeros(N)
     
     for jj in range(N):
         out[jj]= quad( incond , nu[jj] , nu[jj+1] ) [0] / dx

     return out           

    

def initialization( N ):
    
    """Initializes uniform partition of (x0, x1) and approximate operator F_n"""    
    #delta x
    dx = ( x1 - x0 ) / N
    
    #Uniform partition into smaller frames
    nu = x0 + np.arange(N+1) * dx
    
    #Aggregation in
    Ain = np.zeros( ( N , N ) )
    
    #Aggregation out
    Aout = np.zeros( ( N , N ) )
    
    #Fragmentation in
    Fin = np.zeros( ( N , N ) )
    
    #Fragmentation out
    Fout = np.zeros( N )



    #Initialize matrices Ain, Aout,  Fin and Fout
    for mm in range( N ):
    
        for nn in range( N ):
            
            if mm>nn:
            
                Ain[mm,nn] = 0.5 * dx * aggregation( nu[mm] , nu[nn+1] )
            
            if mm + nn < N-1 :
                
                Aout[mm, nn] = dx * aggregation( nu[mm+1] , nu[nn+1] )
                    
            if nn > mm :
            
                Fin[mm, nn] = dx * gam( nu[mm+1], nu[nn+1] ) * fragm( nu[nn+1] )


    #Initialize matrix Fout
    Fout = 0.5 * fragm( nu[range( 1 , N + 1 ) ] ) + rem( nu[range( 1 , N + 1 )] )


    return ( Ain , Aout , Fin, Fout ,  nu , N , dx)


def odeRHS(y , t , Gamma , N ,  Ain, Aout, Fout, nu , dx ):
    
    """Approximate operator for the right hand side of the evolution equation"""
   
    Fin = dx * np.triu(Gamma.T , 1) * fragm( nu[range( 1 , N+1 ) ] )
    
    a = np.zeros_like(y)

    a [ range( 1 , len( a ) ) ] = y [ range( len( y ) - 1 ) ]    


    out = np.sum( Ain * y * lin.toeplitz( np.zeros_like(y) , a).T + 
                  Fin * y - (Aout.T*y).T * y, axis = 1 ) - Fout * y   
    return out


def dataRHS(y , t , N , Ain , Aout , Fin , Fout ):
   
    """RHS of the ode used for data generation"""
    a = np.zeros_like(y)

    a[range(1,len(a))] = y[range(len(y) - 1)]        
    
    return np.sum( Ain * lin.toeplitz( np.zeros_like(y) , a).T * y + Fin * y, axis = 1 ) - \
           np.dot( (Aout.T*y).T , y )- Fout * y     
    

def reverse_cumsum(arr):
    
    """Given a matrix each row cdf of some pdf, converts cdf to pdf for each row"""
    out = np.zeros_like(arr)
    out[:,0] = arr[:,0]
    out[:, 1:] = np.diff( arr , axis=1 )
    return out
    
 

#==============================================================================
# Generate data
#==============================================================================

#Fine grid x used for data generation
fine_N = 1000

#Fine grid t used for data generation
fine_t = 10000

tfinal = 10

Ain, Aout, Fin, Fout, nu, N, dx = initialization( fine_N )
mytime = np.linspace( 0 , tfinal , fine_t )

y0 = ICproj( N )

data_generator = partial( dataRHS , N=N , Ain=Ain , Aout=Aout , Fin=Fin , Fout=Fout )           
mydata = odeint( data_generator , y0 , mytime ,  rtol=1e-6, atol=1e-6 )

interp_x  = np.linspace( x0 , x1 , fine_N )
interp_func = interpolate.interp2d( interp_x , mytime , mydata )


def interp_data( nu , mytime , mu=0 , sigma=20 ):

    """Interpolates the data to the given grid nu and mytime"""
    
    data = np.zeros( ( len(mytime) , len(nu) - 1 ) )
    
    for mm in range( len(nu) - 1):
        
        int_grid = np.linspace( nu[mm] , nu[mm+1] )
        
        data[ : , mm] = np.trapz( interp_func( int_grid , mytime ) , int_grid , axis=1 )
        
    #Add some normally distributed error
    if sigma>0:    
        noise = np.random.normal( mu , sigma , data.shape )
        data += noise
        
    return data

   
